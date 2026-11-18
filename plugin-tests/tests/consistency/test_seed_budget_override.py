"""The seeded protected-budget sentence a change opts in to with `Budget: protected`.

Two budget sentences are seeded: the repo's own (protected or lean) and the one a single change
uses when its proposal carries `Budget: protected`. The checker reads both; the seed script lists
either as missing when a config lacks it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / ".claude" / "plugins" / "cla" / "skills" / "cla-setup" / "scripts" / "seed_openspec_rules.py"
_CONFIG = _REPO / "openspec" / "config.yaml"


def _seed(root: Path) -> str:
    out = subprocess.run([sys.executable, "-I", str(_SCRIPT), str(root)], capture_output=True, timeout=120)
    assert out.returncode == 0, out.stderr.decode("utf-8", errors="replace")
    return out.stdout.decode("utf-8")


def _override_line(text: str) -> str:
    return next(line for line in text.splitlines() if "`Budget: protected`" in line)


# requirement: cla-setup / Stakes and change budget on setup
def test_the_lean_seed_keeps_the_protected_numbers_for_the_override(tmp_path: Path):
    (tmp_path / "openspec").mkdir()
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text("- Change budget: lean\n", encoding="utf-8")
    _seed(tmp_path)
    written = (tmp_path / "openspec" / "config.yaml").read_text(encoding="utf-8")
    assert "at most 12 requirements across all its specs" in written
    override = _override_line(written)
    assert "at most 25 requirements across all its specs" in override and "at most 6,000 words in total" in override
    assert override.strip() == _override_line(_CONFIG.read_text(encoding="utf-8")).strip()


# requirement: cla-setup / Stakes and change budget on setup
def test_a_config_with_a_repo_budget_but_no_override_is_listed_as_missing_it(tmp_path: Path):
    text = _CONFIG.read_text(encoding="utf-8")
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_text(text.replace(_override_line(text) + "\n", ""), encoding="utf-8", newline="\n")
    out = _seed(tmp_path).splitlines()
    assert len(out) == 2 and out[1] == "+ proposal: " + _override_line(text).strip()


# requirement: cla-setup / Stakes and change budget on setup
def test_a_config_with_only_the_override_is_still_listed_as_missing_the_repo_budget(tmp_path: Path):
    text = _CONFIG.read_text(encoding="utf-8")
    repo_line = next(line for line in text.splitlines() if "within its budget" in line and "`Budget: protected`" not in line)
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_text(text.replace(repo_line + "\n", ""), encoding="utf-8", newline="\n")
    out = _seed(tmp_path).splitlines()
    assert len(out) == 2 and out[1] == "+ proposal: " + repo_line.strip()


def _repo_budget_line(text: str) -> str:
    return next(line for line in text.splitlines() if "within its budget" in line and "`Budget: protected`" not in line)


# requirement: cla-setup / Stakes and change budget on setup
def test_a_capitalised_budget_sentence_still_counts_as_the_budget(tmp_path: Path):
    text = _CONFIG.read_text(encoding="utf-8")
    repo_line = _repo_budget_line(text)
    edited = repo_line.replace("at most 25 requirements", "At most 30 requirements")
    assert edited != repo_line
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_text(text.replace(repo_line, edited), encoding="utf-8", newline="\n")
    assert _seed(tmp_path).splitlines() == ["openspec/config.yaml: exists (skipped), rules current"]


# requirement: cla-setup / Stakes and change budget on setup
def test_a_commented_out_budget_sentence_does_not_count_as_the_budget(tmp_path: Path):
    text = _CONFIG.read_text(encoding="utf-8")
    repo_line = _repo_budget_line(text)
    edited = repo_line.replace("- ", "# - ", 1).replace("at most 25 requirements", "at most 30 requirements")
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_text(text.replace(repo_line, edited), encoding="utf-8", newline="\n")
    out = _seed(tmp_path).splitlines()
    assert len(out) == 2 and out[1] == "+ proposal: " + repo_line.strip()


# requirement: cla-setup / Stakes and change budget on setup
def test_a_budget_sentence_outside_rules_does_not_count_as_the_budget(tmp_path: Path):
    # The checker reads a budget only under `rules:`; a `context:` block naming one sets none.
    text = _CONFIG.read_text(encoding="utf-8")
    repo_line = _repo_budget_line(text)
    edited = text.replace(repo_line + "\n", "").replace(
        "rules:\n", "context: |\n  " + repo_line.strip().lstrip("- ").strip('"') + "\n\nrules:\n", 1,
    )
    assert "context: |" in edited
    cfg = tmp_path / "openspec" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_text(edited, encoding="utf-8", newline="\n")
    out = _seed(tmp_path).splitlines()
    assert len(out) == 2 and out[1] == "+ proposal: " + repo_line.strip()
