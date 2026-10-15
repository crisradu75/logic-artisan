"""cla-setup seeds the `rules:` block this repo's own `openspec/config.yaml` carries.

The block exists twice: once in `cla-setup/scripts/seed_openspec_rules.py`, the
script the seed item runs to write it into a consuming repo's
`openspec/config.yaml`, and once in this repo's `openspec/config.yaml`, where
OpenSpec injects it into every authoring run here. The config file says "keep the
two in step"; nothing else checks it. If one side is edited, this repo authors
under one set of rules and every consumer under another, and both read fine on
their own.

Scope, stated narrowly: this pins that the two blocks are identical, that an
item containing `: ` is quoted, that no skill carries a third copy of the spec
rules, and that the skill runs the script by its path and holds no copy of the
block. It also runs the script against scratch repos: it seeds a missing
config, and on an existing one (`config.yaml` or `config.yml`) it lists the
shipped rules the file lacks (`+`) and the earlier wordings it still carries
(`-`), never the repo's own lines, and leaves the file byte-identical. The
update the user may then agree to is the model's own edit and is not run here.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SKILL = _REPO / ".claude" / "plugins" / "cla" / "skills" / "cla-setup" / "SKILL.md"
_SCRIPT = _SKILL.parent / "scripts" / "seed_openspec_rules.py"
_CONFIG = _REPO / "openspec" / "config.yaml"


def _script_constant(name: str) -> str:
    # The text of a `NAME = r"""..."""` constant in the seed script, minus its closing newline.
    text = _SCRIPT.read_text(encoding="utf-8")
    match = re.search(rf'^{name} = r"""(.*?)\n""".rstrip\("\\n"\)$', text, re.DOTALL | re.MULTILINE)
    assert match, f"seed_openspec_rules.py: no {name} constant found"
    return match.group(1)


def _shipped_block() -> str:
    return _script_constant("RULES")


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
    assert _shipped_block() == _config_block()


_SKILL_CALL = 'SEED="${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/seed_openspec_rules.py"'


def test_the_skill_runs_the_seed_script_by_path_and_holds_no_copy_of_the_rules():
    # One source for the rules: the script. A copy in the skill would drift from it,
    # and a command pasted into the Bash tool breaks past about 8 KB on Windows.
    text = _SKILL.read_text(encoding="utf-8")
    assert _SCRIPT.is_file()
    assert _SKILL_CALL in text
    assert "RULES=" not in text and "RETIRED=" not in text
    assert "rules:\n  proposal:" not in text.replace("\r\n", "\n")


def _misread_unquoted(line: str) -> bool:
    """An unquoted list item YAML would not read as the plain string it looks like.

    "a: b" or a trailing ":" makes a mapping, and OpenSpec then drops that artifact's
    rules (cla-setup/SKILL.md says so beside the block). " #" starts a comment, so the
    rest of the rule silently vanishes.
    """
    stripped = line.lstrip()
    if not stripped.startswith("- "):
        return False
    item = stripped[2:].rstrip()
    if item.startswith(('"', "'")):
        return False
    return ": " in item or item.endswith(":") or " #" in item


def test_an_item_yaml_would_misread_is_quoted():
    unquoted = [line for line in _shipped_block().splitlines() if _misread_unquoted(line)]
    assert unquoted == []


def test_the_misread_check_catches_each_shape():
    assert _misread_unquoted("    - Keep it short: one line")
    assert _misread_unquoted("    - Trailing colon:")
    assert _misread_unquoted("    - A rule # and its tail")
    assert not _misread_unquoted('    - "Quoted: fine # too"')
    assert not _misread_unquoted("    - 'Single-quoted: fine'")
    assert not _misread_unquoted("    - Plain rule with no traps")


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
        if any(s in p.read_text(encoding="utf-8") for s in _LIMITS)
    ]
    assert len(list(plugin.rglob("*.md"))) > 50, "the scan found too few files to mean anything"
    assert copies == [], f"skills restating `rules.specs`: {copies}"


def _seed(root: Path) -> subprocess.CompletedProcess:
    """Run the seed script on a scratch repo, with the bytes it printed, undecoded."""
    return subprocess.run(
        [sys.executable, "-I", str(_SCRIPT), str(root)], capture_output=True, timeout=120,
    )


def _run_seed(root: Path) -> str:
    out = _seed(root)
    assert out.returncode == 0, out.stderr.decode("utf-8", errors="replace")
    return out.stdout.decode("utf-8")


def _rule_items() -> list[str]:
    return [line for line in _shipped_block().splitlines() if line.startswith("    - ")]


def _retired_block() -> str:
    return _script_constant("RETIRED")


def _retired(fragment: str) -> str:
    return next(line.strip() for line in _retired_block().splitlines() if fragment in line)


_HEADER = "openspec/{}: exists (skipped), missing or outdated rules (+ add, - remove):"


# requirement: repo-context / OpenSpec authoring rules on setup
def test_the_seed_creates_a_missing_config(tmp_path: Path):
    (tmp_path / "openspec").mkdir()
    assert "openspec/config.yaml: created" in _run_seed(tmp_path)
    written = (tmp_path / "openspec" / "config.yaml").read_text(encoding="utf-8")
    assert written == f"schema: spec-driven\n\n{_shipped_block()}\n"


# requirement: repo-context / OpenSpec authoring rules on setup
def test_a_config_with_every_rule_is_reported_current(tmp_path: Path):
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(_CONFIG.read_bytes())
    out = _run_seed(tmp_path)
    assert "openspec/config.yaml: exists (skipped), rules current" in out
    assert cfg.read_bytes() == _CONFIG.read_bytes()


# requirement: repo-context / OpenSpec authoring rules on setup
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
def test_an_earlier_wording_alone_is_listed_for_removal(tmp_path: Path):
    old_rule = _retired("Keep every scenario heading unique")
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(_CONFIG.read_bytes() + f"    {old_rule}\n".encode("utf-8"))
    assert _run_seed(tmp_path).splitlines() == [_HEADER.format("config.yaml"), "- specs: " + old_rule]


# requirement: repo-context / OpenSpec authoring rules on setup
@pytest.mark.parametrize(
    "fragment, artifact",
    [("Keep it to one page. Point", "proposal"), ("Keep it to one page: for each", "design")],
)
def test_an_earlier_cap_wording_is_listed_for_removal(tmp_path: Path, fragment: str, artifact: str):
    old_rule = _retired(fragment)
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(_CONFIG.read_bytes() + f"    {old_rule}\n".encode("utf-8"))
    assert _run_seed(tmp_path).splitlines() == [_HEADER.format("config.yaml"), f"- {artifact}: " + old_rule]


# requirement: repo-context / OpenSpec authoring rules on setup
@pytest.mark.parametrize("trailing", [" ", "\t", "  \r"])
def test_an_earlier_wording_with_trailing_whitespace_is_still_listed(tmp_path: Path, trailing: str):
    old_rule = _retired("Keep it to one page. Point")
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(_CONFIG.read_bytes() + f"    {old_rule}{trailing}\n".encode("utf-8"))
    assert _run_seed(tmp_path).splitlines() == [_HEADER.format("config.yaml"), "- proposal: " + old_rule]


# requirement: repo-context / OpenSpec authoring rules on setup
@pytest.mark.parametrize("quote", ['"', "'"])
@pytest.mark.parametrize("trailing", ["", " "])
def test_a_quoted_copy_of_an_earlier_wording_is_still_listed(tmp_path: Path, quote: str, trailing: str):
    # The shipped retired line is unquoted; a repo may carry the same text inside quotes.
    old_rule = _retired("Keep it to one page. Point")
    assert old_rule.startswith("- ") and not old_rule[2:].startswith(('"', "'"))
    quoted = f"- {quote}{old_rule[2:]}{quote}"
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(_CONFIG.read_bytes() + f"    {quoted}{trailing}\n".encode("utf-8"))
    assert _run_seed(tmp_path).splitlines() == [_HEADER.format("config.yaml"), "- proposal: " + old_rule]


# requirement: repo-context / OpenSpec authoring rules on setup
@pytest.mark.parametrize(
    "shape",
    [
        '- "{}"',  # double quotes
        "- '{}'",  # single quotes
        "- \"'{}'\"",  # both pairs, dropped one after the other
        "\t- {}\t",  # tab padding around the item
    ],
)
def test_every_retired_wording_is_found_in_each_quoted_shape(tmp_path: Path, shape: str):
    """The comparison is one pass over all rules, so each retired line must still be matched."""
    key, expected, carried = "", [], []
    for line in _retired_block().splitlines():
        if line.startswith("  ") and line.endswith(":") and not line.startswith("    "):
            key = line.strip().rstrip(":")
        elif line.startswith("    - "):
            expected.append(f"- {key}: {line.strip()}")
            body = line.strip()[2:]
            # A line already quoted in the list is carried as it is; the shape wraps the plain ones.
            carried.append("    " + (line.strip() if body.startswith('"') else shape.format(body)))
    assert len(expected) >= 7, "the retired list lost its lines"
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(_CONFIG.read_bytes() + ("\n".join(carried) + "\n").encode("utf-8"))
    assert _run_seed(tmp_path).splitlines() == [_HEADER.format("config.yaml"), *expected]


# requirement: repo-context / OpenSpec authoring rules on setup
def test_the_rules_missing_are_listed_in_shipped_order_with_their_artifact(tmp_path: Path):
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(b"rules:\n  specs:\n    - A rule of this repo's own.\n")
    out = _run_seed(tmp_path).splitlines()
    key, expected = "", []
    for line in _shipped_block().splitlines():
        if line.startswith("  ") and line.endswith(":") and not line.startswith("    "):
            key = line.strip().rstrip(":")
        elif line.startswith("    - "):
            expected.append(f"+ {key}: {line.strip()}")
    assert out == [_HEADER.format("config.yaml"), *expected]


# requirement: repo-context / OpenSpec authoring rules on setup
def test_a_config_over_200_kb_is_compared_right(tmp_path: Path):
    """A large config is read whole and compared right (no size limit on the file)."""
    old_rule = _retired("Keep it to one page. Point")
    own = "".join(f"    - A rule of this repo's own, number {i}, padded out to make the file long.\n" for i in range(3000))
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(_CONFIG.read_bytes() + own.encode("utf-8") + f"    {old_rule}\n".encode("utf-8"))
    assert cfg.stat().st_size > 200_000
    assert _run_seed(tmp_path).splitlines() == [_HEADER.format("config.yaml"), "- proposal: " + old_rule]


# requirement: repo-context / OpenSpec authoring rules on setup
def test_a_backslash_in_a_config_rule_line_is_read_as_typed(tmp_path: Path):
    """A literal backslash in a rule line must not be read as an escape."""
    old_rule = _retired("Keep it to one page. Point")
    own = ["    - A rule with a backslash \\n and \\\\ and C:\\temp\\new in it."]
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(_CONFIG.read_bytes() + ("\n".join([*own, f"    {old_rule}"]) + "\n").encode("utf-8"))
    assert _run_seed(tmp_path).splitlines() == [_HEADER.format("config.yaml"), "- proposal: " + old_rule]


# requirement: repo-context / OpenSpec authoring rules on setup
def test_an_unreadable_config_is_reported_and_never_read_as_rules_current(tmp_path: Path):
    # A directory named config.yaml exists but cannot be read as a file.
    (tmp_path / "openspec" / "config.yaml").mkdir(parents=True)
    out = _seed(tmp_path)
    text = out.stdout.decode("utf-8")
    assert out.returncode == 1
    assert "rules current" not in text
    assert "openspec/config.yaml: exists (skipped), rules NOT compared: cannot read it" in text


# requirement: repo-context / OpenSpec authoring rules on setup
def test_without_an_openspec_directory_nothing_is_created_and_the_block_is_printed(tmp_path: Path):
    out = _run_seed(tmp_path)
    assert out.startswith("openspec/config.yaml: not written, no openspec/")
    assert out.rstrip("\n").endswith(_shipped_block().rstrip("\n"))
    assert list(tmp_path.iterdir()) == []


def test_the_seed_script_refuses_a_call_without_a_repo_root():
    out = subprocess.run([sys.executable, "-I", str(_SCRIPT)], capture_output=True, timeout=120)
    assert out.returncode == 2 and out.stdout == b""


# requirement: repo-context / OpenSpec authoring rules on setup
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


# requirement: repo-context / OpenSpec authoring rules on setup
def test_a_utf16_config_is_reported_unreadable_not_listed_as_missing_every_rule(tmp_path: Path):
    # A PowerShell redirect writes UTF-16; read as UTF-8 it matches no rule.
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    original = _CONFIG.read_text(encoding="utf-8").encode("utf-16")
    cfg.write_bytes(original)
    out = _seed(tmp_path)
    text = out.stdout.decode("utf-8")
    assert out.returncode == 1 and "rules NOT compared: cannot read it (not UTF-8 text)" in text
    assert "rules current" not in text and "\n+ " not in text
    assert cfg.read_bytes() == original


# requirement: repo-context / OpenSpec authoring rules on setup
def test_a_utf8_byte_order_mark_does_not_hide_a_current_config(tmp_path: Path):
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(b"\xef\xbb\xbf" + _CONFIG.read_bytes())
    assert "exists (skipped), rules current" in _run_seed(tmp_path)


# requirement: repo-context / OpenSpec authoring rules on setup
def test_a_write_that_fails_after_the_file_is_created_leaves_no_partial_config(tmp_path: Path, capfd, monkeypatch):
    import builtins
    import importlib.util

    spec = importlib.util.spec_from_file_location("seed_openspec_rules_under_test", _SCRIPT)
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    real_open = builtins.open

    class _Failing:
        def __init__(self, handle):
            self._handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._handle.close()

        def write(self, _text):
            self._handle.write("schema: spec")  # a partial write, then the disk fills
            raise OSError("disk full")

    seed.open = lambda *a, **k: _Failing(real_open(*a, **k))  # the module's own `open`, not the builtin
    (tmp_path / "openspec").mkdir()
    assert seed.main(["seed", str(tmp_path)]) == 1
    out = capfd.readouterr().out
    assert "write FAILED" in out and "created" not in out
    assert not (tmp_path / "openspec" / "config.yaml").exists()


# requirement: repo-context / OpenSpec authoring rules on setup
def test_an_existing_config_is_never_removed_when_the_create_is_refused(tmp_path: Path, monkeypatch):
    # A dangling link, or a file made between the check and the create, reaches the create as "already
    # there". Make the check say "absent" for a file that is present, and the create must refuse it.
    import importlib.util

    spec = importlib.util.spec_from_file_location("seed_openspec_rules_under_test2", _SCRIPT)
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_bytes(b"mine\n")
    real_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda self: False if self == cfg else real_exists(self))
    assert seed.main(["seed", str(tmp_path)]) == 1
    monkeypatch.undo()
    assert cfg.read_bytes() == b"mine\n"


_bash = shutil.which("bash")


def _skill_item_5_block() -> str:
    text = _SKILL.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = re.search(r"```bash\n(: \"\$\{ROOT:\?[^`]*?seed_openspec_rules[^`]*?)```", text)
    assert match, "cla-setup/SKILL.md: no item 5 block found"
    return match.group(1)


def _run_item_5(root: Path, plugin_root: str) -> subprocess.CompletedProcess:
    script = _skill_item_5_block().replace("${CLAUDE_PLUGIN_ROOT}", plugin_root)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
    return subprocess.run([_bash, "-c", script], env={**env, "ROOT": root.as_posix()},
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


_needs_bash = pytest.mark.skipif(_bash is None or shutil.which("python3") is None, reason="bash and python3 are required")


# requirement: repo-context / OpenSpec authoring rules on setup
@_needs_bash
def test_the_skills_command_runs_the_script_and_says_so_when_the_plugin_root_is_unresolved(tmp_path: Path):
    (tmp_path / "openspec").mkdir()
    plugin = _SKILL.parents[2].as_posix()
    ok = _run_item_5(tmp_path, plugin)
    assert ok.returncode == 0 and "openspec/config.yaml: created" in ok.stdout, ok.stderr
    (tmp_path / "openspec" / "config.yaml").unlink()
    # An unsubstituted `${CLAUDE_PLUGIN_ROOT}` expands to nothing in the shell.
    lost = _run_item_5(tmp_path, "")
    assert lost.returncode != 0 and "NOT checked, seed script not found" in lost.stdout
    assert not (tmp_path / "openspec" / "config.yaml").exists()
