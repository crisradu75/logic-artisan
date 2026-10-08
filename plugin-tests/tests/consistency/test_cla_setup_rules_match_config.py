"""cla-setup seeds the `rules:` block this repo's own `openspec/config.yaml` carries.

The block exists twice: once in `cla-setup/SKILL.md`, as the heredoc the seed
item writes into a consuming repo's `openspec/config.yaml`, and once in this
repo's `openspec/config.yaml`, where OpenSpec injects it into every authoring run
here. The config file says "keep the two in step"; nothing else checks it. If one
side is edited, this repo authors under one set of rules and every consumer
under another, and both read fine on their own.

Scope, stated narrowly: this pins that the two blocks are identical, that an
item containing `: ` is quoted, that no skill carries a third copy of the spec
rules, and that the seed condition treats an existing `config.yml` as a config.
It also runs the seed item, a bash block the model executes, against scratch
repos: it seeds a missing config, and on an existing one it lists the shipped
rules the file lacks (`+`) and the earlier wordings it still carries (`-`),
never the repo's own lines, and leaves the file byte-identical. The update the
user may then agree to is the model's own edit and is not run here.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SKILL = _REPO / ".claude" / "plugins" / "cla" / "skills" / "cla-setup" / "SKILL.md"
_CONFIG = _REPO / "openspec" / "config.yaml"


def _skill_block() -> str:
    text = _SKILL.read_text(encoding="utf-8")
    match = re.search(r"RULES=\"\$\(cat <<'EOF'\n(.*?)\nEOF\n", text, re.DOTALL)
    assert match, "cla-setup/SKILL.md: no RULES heredoc found"
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


# requirement: change-workflow / Specs follow the repo's authoring rules
def test_cla_setup_seeds_the_block_this_repo_carries():
    assert _skill_block() == _config_block()


def test_the_seed_treats_config_yml_as_existing():
    # OpenSpec reads config.yaml before config.yml, so seeding config.yaml
    # beside an existing config.yml would hide the user's file.
    text = _SKILL.read_text(encoding="utf-8")
    assert '[ ! -e "$CFG" ] && [ ! -e "$ROOT/openspec/config.yml" ]' in text


def test_an_item_with_a_colon_is_quoted():
    # Unquoted, YAML reads "a: b" as a mapping and OpenSpec drops that
    # artifact's rules (cla-setup/SKILL.md says so beside the block).
    unquoted = [
        line
        for line in _skill_block().splitlines()
        if line.lstrip().startswith("- ")
        and ": " in line
        and not line.lstrip()[2:].startswith('"')
    ]
    assert unquoted == []


# Each limit as a restatement would spell it: "500 characters", "at most 3
# scenarios", "up to 8 requirements per spec".
_LIMITS = ("500 char", "≤500", "3 scenarios", "8 requirements")


def test_no_skill_carries_a_third_copy_of_the_spec_rules():
    # `openspec/config.yaml` is the single source; skills point at it. A copy
    # in a skill drifts from it, and both read fine on their own.
    plugin = _SKILL.parents[2]
    copies = [
        str(p.relative_to(_REPO))
        for p in plugin.rglob("*.md")
        if p != _SKILL and any(s in p.read_text(encoding="utf-8") for s in _LIMITS)
    ]
    assert len(list(plugin.rglob("*.md"))) > 50, "the scan found too few files to mean anything"
    assert copies == [], f"skills restating `rules.specs`: {copies}"


_BASH = shutil.which("bash")


def _seed_script() -> str:
    text = _SKILL.read_text(encoding="utf-8")
    match = re.search(r"```bash\n(: \"\$\{ROOT:\?.*?RULES=\"\$\(cat <<'EOF'\n.*?)```", text, re.DOTALL)
    assert match, "cla-setup/SKILL.md: no seed script found"
    return match.group(1)


def _run_seed(root: Path) -> str:
    out = subprocess.run(
        [_BASH, "-c", _seed_script()],
        # Forward slashes: a POSIX shell reads `C:\...` backslashes as escapes.
        env={**os.environ, "ROOT": str(root).replace("\\", "/")},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


def _rule_items() -> list[str]:
    return [line for line in _skill_block().splitlines() if line.startswith("    - ")]


def _retired(fragment: str) -> str:
    text = _SKILL.read_text(encoding="utf-8")
    match = re.search(r"RETIRED=\"\$\(cat <<'EOF'\n(.*?)\nEOF\n", text, re.DOTALL)
    assert match, "cla-setup/SKILL.md: no RETIRED heredoc found"
    return next(line.strip() for line in match.group(1).splitlines() if fragment in line)


_HEADER = "openspec/{}: exists (skipped), missing or outdated rules (+ add, - remove):"


_needs_bash = pytest.mark.skipif(_BASH is None, reason="bash is not installed")


# requirement: repo-context / OpenSpec authoring rules on setup
@_needs_bash
def test_the_seed_creates_a_missing_config(tmp_path: Path):
    (tmp_path / "openspec").mkdir()
    assert "openspec/config.yaml: created" in _run_seed(tmp_path)
    written = (tmp_path / "openspec" / "config.yaml").read_text(encoding="utf-8")
    assert written == f"schema: spec-driven\n\n{_skill_block()}\n"


# requirement: repo-context / OpenSpec authoring rules on setup
@_needs_bash
def test_a_config_with_every_rule_is_reported_current(tmp_path: Path):
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(_CONFIG.read_bytes())
    out = _run_seed(tmp_path)
    assert "openspec/config.yaml: exists (skipped), rules current" in out
    assert cfg.read_bytes() == _CONFIG.read_bytes()


# requirement: repo-context / OpenSpec authoring rules on setup
@_needs_bash
def test_an_outdated_rule_is_listed_and_the_file_left_alone(tmp_path: Path):
    items = _rule_items()
    tasks_rule = next(i for i in items if "requirement: <spec> / <heading>" in i)
    old_tasks_rule = _retired("`scenario: <spec> / <heading>`")
    # A shipped earlier wording in place of the tasks rule, the repo's own rule
    # (one reading like a shipped rule), CRLF line endings and a different
    # indent: the new rule is listed to add, the earlier wording to remove,
    # and the repo's own lines not at all.
    lines = ["schema: spec-driven", "rules:"]
    for item in items:
        lines.append("  " + (item if item != tasks_rule else old_tasks_rule).strip())
    lines += ["  - A rule of this repo's own.", '  - "Give each scenario a test."']
    original = ("\r\n".join(lines) + "\r\n").encode("utf-8")
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(original)
    out = _run_seed(tmp_path)
    assert out.splitlines() == [
        _HEADER.format("config.yaml"),
        "+ tasks: " + tasks_rule.strip(),
        "- tasks: " + old_tasks_rule,
    ]
    assert cfg.read_bytes() == original


# requirement: repo-context / OpenSpec authoring rules on setup
@_needs_bash
def test_an_earlier_wording_alone_is_listed_for_removal(tmp_path: Path):
    old_rule = _retired("Keep every scenario heading unique")
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(_CONFIG.read_bytes() + f"    {old_rule}\n".encode("utf-8"))
    assert _run_seed(tmp_path).splitlines() == [_HEADER.format("config.yaml"), "- specs: " + old_rule]


# requirement: repo-context / OpenSpec authoring rules on setup
@_needs_bash
def test_a_config_yml_is_compared_and_no_config_yaml_is_created(tmp_path: Path):
    yml = tmp_path / "openspec" / "config.yml"
    yml.parent.mkdir()
    yml.write_text("schema: spec-driven\n", encoding="utf-8")
    out = _run_seed(tmp_path).splitlines()
    assert out[0] == _HEADER.format("config.yml")
    assert len(out) == 1 + len(_rule_items())
    assert all(line.startswith("+ ") for line in out[1:])
    assert not (tmp_path / "openspec" / "config.yaml").exists()
    assert yml.read_text(encoding="utf-8") == "schema: spec-driven\n"
