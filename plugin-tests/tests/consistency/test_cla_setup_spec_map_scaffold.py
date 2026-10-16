"""cla-setup offers a three-layer spec map scaffold, asks first, and the scaffold passes the checker once filled.

The offer is prose a model follows, so what a test can pin is the scaffold text itself: it names the
three layers in order, and when its "Specs not yet placed" list is filled with one link per live spec
(as the skill tells the model to do) `check_spec_proof.py` accepts it. Unfilled, the same file is
reported, which shows that the list is what carries the weight.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_PLUGIN = _REPO / ".claude" / "plugins" / "cla"
_SKILL = _PLUGIN / "skills" / "cla-setup" / "SKILL.md"
_SCRIPT = _PLUGIN / "skills" / "_shared" / "scripts" / "check_spec_proof.py"
_spec = importlib.util.spec_from_file_location("check_spec_proof_scaffold", _SCRIPT)
csp = importlib.util.module_from_spec(_spec)
sys.modules["check_spec_proof_scaffold"] = csp
_spec.loader.exec_module(csp)


def _section() -> str:
    text = _SKILL.read_text(encoding="utf-8")
    m = re.search(r"### The spec map scaffold\n(.*?)\n### 8\. ", text, re.S)
    assert m, "cla-setup/SKILL.md: no 'The spec map scaffold' section"
    return m.group(1)


def _scaffold() -> str:
    m = re.search(r"````markdown\n(.*?)````", _section(), re.S)
    assert m, "the scaffold section holds no four-backtick markdown block"
    return m.group(1)


def _repo_with(tmp_path: Path, map_text: str) -> Path:
    root = tmp_path / "r"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True, capture_output=True)
    for name in ("alpha", "beta"):
        d = root / "openspec" / "specs" / name
        d.mkdir(parents=True)
        (d / "spec.md").write_text(
            f"# {name}\n\n## Purpose\n\nx\n\n## Requirements\n\n### Requirement: R\n\nSHALL.\n\n"
            "#### Scenario: S\n\n- **WHEN** a\n- **THEN** b\n",
            encoding="utf-8",
            newline="\n",
        )
    (root / "tests").mkdir()
    (root / "tests" / "t.py").write_text("# requirement: alpha / R\n# requirement: beta / R\n", encoding="utf-8", newline="\n")
    (root / "cla.io").mkdir()
    (root / "cla.io" / "project-facts.md").write_text("## Spec map\n\n- openspec/spec-map.md\n", encoding="utf-8", newline="\n")
    (root / "openspec" / "spec-map.md").write_text(map_text, encoding="utf-8", newline="\n")
    return root


def _check(root: Path) -> tuple[int, list[str]]:
    return csp.check(root, base_arg=None)


# requirement: spec-map / Setup offers a three-layer spec map scaffold
def test_the_scaffold_names_the_three_layers_in_order():
    s = _scaffold()
    layers = [s.index(h) for h in ("## Capabilities", "## Workflows", "## Specs not yet placed")]
    assert layers == sorted(layers)
    assert "Links only" in s


# requirement: spec-map / Setup offers a three-layer spec map scaffold
def test_the_scaffold_filled_with_one_link_per_live_spec_passes_the_checker(tmp_path):
    placeholder = "- [<spec name>](<path to openspec/specs/<spec name>/spec.md, relative to this file>)"
    scaffold = _scaffold()
    assert placeholder in scaffold
    filled = scaffold.replace(placeholder, "\n".join(f"- [{n}](specs/{n}/spec.md)" for n in ("alpha", "beta")))
    code, lines = _check(_repo_with(tmp_path, filled))
    assert code == 0 and not [ln for ln in lines if ln.startswith("PROBLEM")]


# requirement: spec-map / Setup offers a three-layer spec map scaffold
def test_the_unfilled_scaffold_is_reported_for_every_live_spec(tmp_path):
    code, lines = _check(_repo_with(tmp_path, _scaffold()))
    assert code == 1
    unlinked = [ln for ln in lines if "linked from no spec map" in ln]
    assert len(unlinked) == 2


# requirement: spec-map / Setup offers a three-layer spec map scaffold
def test_the_skill_asks_before_writing_and_never_imposes_a_path():
    s = _section()
    assert "never imposes" in s and "Offer once per run" in s and "openspec/spec-map.md" in s
    assert "never overwritten" in s and "Write no map and no heading" in s
