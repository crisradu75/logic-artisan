"""cla-setup: the Test proof question, the echoing seed idioms, the clean spec-map scaffold, and
the granularity-aware OpenSpec tasks rule.

Each test pins one of four fixes: the skill asks for the Test proof granularity (items 10 and 13);
every pinned seed idiom reports `created` or `exists (skipped)`; the spec-map scaffold passes
`check_spec_proof.py` as written; and `seed_openspec_rules.py` never offers two contradictory
`tasks` rules.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[4]
_PLUGIN = _REPO / ".claude" / "plugins" / "cla"
_SKILL = _PLUGIN / "skills" / "cla-setup" / "SKILL.md"
_SEED = _PLUGIN / "skills" / "cla-setup" / "scripts" / "seed_openspec_rules.py"
_CHECKER = _PLUGIN / "skills" / "_shared" / "scripts" / "check_spec_proof.py"

_bash = shutil.which("bash")
_needs_bash = pytest.mark.skipif(_bash is None, reason="bash is required")


def _text() -> str:
    return _SKILL.read_text(encoding="utf-8").replace("\r\n", "\n")


def _section(start: str, end: str) -> str:
    text = _text()
    a = text.index(start)
    return text[a : text.index(end, a)]


# requirement: repo-context / Repo facts and overlay rules on setup
def test_item_13_asks_the_granularity_question_and_item_10_drafts_the_line():
    item_13 = _section("### 13. Confirm, write, check", "**Then run the staleness checker")
    item_10 = _section("### 10. Draft the changes", "### 11.")
    for part in (item_13, item_10):
        assert "Test proof granularity" in part and "`## Test proof`" in part
    assert "recommended" in item_13 and "`requirement`" in item_13
    assert "- Test proof granularity: requirement" in item_10


# requirement: repo-context / Setting up a repo's cla.io tree and economy rules file
@_needs_bash
def test_every_part_1_seed_idiom_reports_created_then_exists(tmp_path: Path):
    part_1 = _section("### 1. `cla.io/` directories", "### 5. OpenSpec authoring rules")
    blocks = re.findall(r"```bash\n(.*?)```", part_1, re.DOTALL)
    assert len(blocks) == 4
    script = "\n".join(blocks)
    env = {"ROOT": tmp_path.as_posix(), "PATH": __import__("os").environ["PATH"]}

    def run() -> list[str]:
        out = subprocess.run([_bash, "-c", script], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        assert out.returncode == 0, out.stderr
        return out.stdout.splitlines()

    first = run()
    targets = ["decisions", "feedback", "retro", "lessons-learned"]
    assert [l for l in first if l.startswith("created: ")] == first and len(first) == 7
    assert (tmp_path / "cla.io" / "retro" / "spec-to-pr-runs.jsonl").read_bytes() == b""
    notes = tmp_path / "cla.io" / "feedback" / "notes.md"
    notes.write_text("mine\n", encoding="utf-8")
    ledger = tmp_path / "cla.io" / "retro" / "spec-to-pr-runs.jsonl"
    ledger.write_text("{}\n", encoding="utf-8")
    second = run()
    assert len(second) == 7 and all(l.startswith("exists (skipped): ") for l in second)
    assert notes.read_text(encoding="utf-8") == "mine\n" and ledger.read_text(encoding="utf-8") == "{}\n"
    assert all((tmp_path / "cla.io" / t).is_dir() for t in targets)


def test_the_pinned_idioms_in_the_contract_echo_their_outcome():
    contract = _section("- **The guard is load-bearing.**", "- **Create only what is missing.**")
    assert contract.count('echo "exists (skipped)') == 3 and contract.count('echo "created') == 3
    assert "|| cat >" not in contract and "|| : >" not in contract


# requirement: repo-context / Repo facts and overlay rules on setup
def test_the_spec_map_scaffold_passes_the_checker_as_written(tmp_path: Path):
    scaffold = re.search(r"````markdown\n(.*?)````", _text(), re.DOTALL).group(1)
    # The placeholders carry no link, so only the bullet under "Specs not yet placed" is one.
    assert scaffold.count("](") == 1 and "(#" not in scaffold
    spec = tmp_path / "openspec" / "specs" / "alpha" / "spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "# alpha\n\n## Purpose\n**Serves:** testers.\n\n## Requirements\n\n### Requirement: It works\n"
        "The thing SHALL work.\n\n#### Scenario: Works\n- **WHEN** run\n- **THEN** it works\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_alpha.py").write_text("# requirement: alpha / It works\ndef test_a(): pass\n", encoding="utf-8")
    # What the skill writes: the scaffold with one real bullet for the spec, at the chosen path.
    placed = scaffold.replace(
        "- [<spec name>](<path to openspec/specs/<spec name>/spec.md, relative to this file>)",
        "- [alpha](specs/alpha/spec.md)",
    )
    assert placed != scaffold
    (tmp_path / "openspec" / "spec-map.md").write_text(placed, encoding="utf-8")
    facts = tmp_path / "cla.io" / "project-facts.md"
    facts.parent.mkdir()
    facts.write_text("# Facts\n\n## Spec map\n\n- openspec/spec-map.md\n", encoding="utf-8")
    out = subprocess.run([sys.executable, "-I", str(_CHECKER), "--root", str(tmp_path)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert out.returncode == 0 and "PROBLEM" not in out.stdout, out.stdout + out.stderr


# ---- seed_openspec_rules.py: granularity-aware tasks rule ----

_HEADER = "openspec/config.yaml: exists (skipped), missing or outdated rules (+ add, - remove):"


def _const(name: str) -> str:
    text = _SEED.read_text(encoding="utf-8")
    m = re.search(rf'^{name} = r"""(.*?)\n""".rstrip\("\\n"\)$', text, re.DOTALL | re.MULTILINE)
    assert m
    return m.group(1)


def _scenario_task() -> str:
    m = re.search(r"^SCENARIO_TASK = r'''(.*?)'''$", _SEED.read_text(encoding="utf-8"), re.DOTALL | re.MULTILINE)
    assert m
    return m.group(1)


def _requirement_task() -> str:
    return next(l for l in _const("RULES").splitlines() if "requirement: <spec> / <heading>" in l)


def _seed(root: Path) -> str:
    out = subprocess.run([sys.executable, "-I", str(_SEED), str(root)], capture_output=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return out.stdout.decode("utf-8")


def _repo(tmp_path: Path, granularity: str | None, config: str | None) -> Path:
    (tmp_path / "openspec").mkdir()
    if config is not None:
        (tmp_path / "openspec" / "config.yaml").write_text(config, encoding="utf-8", newline="\n")
    if granularity is not None:
        (tmp_path / "cla.io").mkdir()
        (tmp_path / "cla.io" / "project-facts.md").write_text(
            f"# Facts\n\n## Test proof\n\n- Test proof granularity: {granularity}\n", encoding="utf-8"
        )
    return tmp_path


def _config_with(task: str) -> str:
    rules = _const("RULES").replace(_requirement_task(), task)
    return f"schema: spec-driven\n\n{rules}\n"


def test_the_scenario_wording_is_also_the_requirement_repos_earlier_wording():
    assert _scenario_task() in _const("RETIRED").splitlines()


# requirement: repo-context / OpenSpec authoring rules on setup
def test_a_scenario_repo_is_not_offered_the_requirement_rule(tmp_path: Path):
    repo = _repo(tmp_path, "scenario", _config_with(_scenario_task()))
    assert "rules current" in _seed(repo)


# requirement: repo-context / OpenSpec authoring rules on setup
def test_a_scenario_repo_holding_the_requirement_rule_is_told_to_swap_it(tmp_path: Path):
    repo = _repo(tmp_path, "scenario", _config_with(_requirement_task()))
    assert _seed(repo).splitlines() == [
        _HEADER, "+ tasks: " + _scenario_task().strip(), "- tasks: " + _requirement_task().strip(),
    ]


# requirement: repo-context / OpenSpec authoring rules on setup
def test_a_requirement_repo_holding_the_scenario_rule_is_told_to_swap_it(tmp_path: Path):
    repo = _repo(tmp_path, "requirement", _config_with(_scenario_task()))
    assert _seed(repo).splitlines() == [
        _HEADER, "+ tasks: " + _requirement_task().strip(), "- tasks: " + _scenario_task().strip(),
    ]


# requirement: repo-context / OpenSpec authoring rules on setup
def test_no_facts_line_means_requirement(tmp_path: Path):
    repo = _repo(tmp_path, None, _config_with(_requirement_task()))
    assert "rules current" in _seed(repo)


# requirement: repo-context / OpenSpec authoring rules on setup
def test_a_scenario_repo_is_seeded_with_the_scenario_rule_only(tmp_path: Path):
    repo = _repo(tmp_path, "scenario", None)
    assert "openspec/config.yaml: created" in _seed(repo)
    written = (repo / "openspec" / "config.yaml").read_text(encoding="utf-8")
    assert _scenario_task() in written.splitlines() and _requirement_task() not in written.splitlines()
    assert written.count("  tasks:") == 1


@pytest.mark.parametrize("granularity", ["requirement", "scenario"])
def test_the_report_never_lists_both_tasks_rules_as_missing(tmp_path: Path, granularity: str):
    repo = _repo(tmp_path, granularity, "schema: spec-driven\n")
    adds = [l for l in _seed(repo).splitlines() if l.startswith("+ tasks: ") and ("requirement: <spec>" in l or "scenario: <spec>" in l)]
    assert len(adds) == 1
