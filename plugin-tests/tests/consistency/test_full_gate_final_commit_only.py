"""The `Full gate: final-commit-only` fact is stated at every site that reads it.

A repo with a slow full gate writes `- Full gate: final-commit-only` in `cla.io/project-facts.md`.
spec-to-pr's Test phase then runs smoke and touched tests only, the one full gate runs after
Archive, and multi-pr's pre-merge gate counts as that run. Prose a model reads, so this pins what
text can show: each site names the fact, and the Test phase keeps its two ends (the post-Archive
run and the multi-pr skip).
"""

from __future__ import annotations

from pathlib import Path

import pytest

_SKILLS = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "skills"
FACT = "Full gate: final-commit-only"

_SITES = {
    "spec-to-pr Test": _SKILLS / "spec-to-pr" / "SKILL.md",
    "multi-pr change loop": _SKILLS / "multi-pr" / "references" / "change-loop.md",
    "chain-merge": _SKILLS / "_shared" / "references" / "chain-merge.md",
    "cla-setup": _SKILLS / "cla-setup" / "references" / "facts-file.md",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


@pytest.mark.parametrize("site", sorted(_SITES))
def test_every_site_names_the_fact(site: str) -> None:
    assert FACT in _read(_SITES[site]), f"{site} no longer names `{FACT}`"


def test_the_test_phase_keeps_both_ends_of_the_rule() -> None:
    text = _read(_SITES["spec-to-pr Test"])
    para = text.split(f"**`{FACT}`.**", 1)[1].split("\n\n", 1)[0]
    for wanted in ("smoke and the touched tests only", "after Archive's push post-check", "orchestration-economy.md", "names `/cla:multi-pr` as its caller", "`ok` to `warn`", "The line absent"):
        assert wanted in para, f"the Full gate paragraph lost {wanted!r}"


def test_multi_pr_tells_spec_to_pr_it_is_the_caller() -> None:
    assert "Name `/cla:multi-pr` as the caller" in _read(_SITES["multi-pr change loop"])
