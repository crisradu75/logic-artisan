"""cla-init seeds the `rules:` block this repo's own `openspec/config.yaml` carries.

The block exists twice: once in `cla-init/SKILL.md`, as the heredoc the seed
item writes into a consuming repo's `openspec/config.yaml`, and once in this
repo's `openspec/config.yaml`, where OpenSpec injects it into every authoring run
here. The config file says "keep the two in step"; nothing else checks it. If one
side is edited, this repo authors under one set of rules and every consumer
under another, and both read fine on their own.

Scope, stated narrowly: this pins that the two blocks are identical, that an
item containing `: ` is quoted, and that the seed condition treats an existing
`config.yml` as a config. It does not run the seed item, which is a
bash block the model executes (proven by hand, tasks 8.3).
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SKILL = _REPO / ".claude" / "plugins" / "cla" / "skills" / "cla-init" / "SKILL.md"
_CONFIG = _REPO / "openspec" / "config.yaml"


def _skill_block() -> str:
    text = _SKILL.read_text(encoding="utf-8")
    match = re.search(r"RULES=\"\$\(cat <<'EOF'\n(.*?)\nEOF\n", text, re.DOTALL)
    assert match, "cla-init/SKILL.md: no RULES heredoc found"
    return match.group(1).rstrip()


def _config_block() -> str:
    text = _CONFIG.read_text(encoding="utf-8")
    start = text.find("\nrules:\n")
    assert start != -1, "openspec/config.yaml: no top-level rules: block"
    # The block runs to the next top-level key, or to the end of the file.
    rest = text[start + 1 :]
    end = re.search(r"\n(?=[^\s#])", rest[len("rules:\n") :])
    block = rest if end is None else rest[: len("rules:\n") + end.start()]
    return block.rstrip()


def test_cla_init_seeds_the_block_this_repo_carries():
    assert _skill_block() == _config_block()


def test_the_seed_treats_config_yml_as_existing():
    # OpenSpec reads config.yaml before config.yml, so seeding config.yaml
    # beside an existing config.yml would hide the user's file.
    text = _SKILL.read_text(encoding="utf-8")
    assert '[ ! -e "$CFG" ] && [ ! -e "$ROOT/openspec/config.yml" ]' in text


def test_an_item_with_a_colon_is_quoted():
    # Unquoted, YAML reads "a: b" as a mapping and OpenSpec drops that
    # artifact's rules (cla-init/SKILL.md says so beside the block).
    unquoted = [
        line
        for line in _skill_block().splitlines()
        if line.lstrip().startswith("- ")
        and ": " in line
        and not line.lstrip()[2:].startswith('"')
    ]
    assert unquoted == []
