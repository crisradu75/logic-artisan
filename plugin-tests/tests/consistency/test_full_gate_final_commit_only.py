"""The `Full gate: final-commit-only` fact is stated at every site that reads it.

A repo with a slow full gate writes `- Full gate: final-commit-only` in `cla.io/project-facts.md`.
spec-to-pr's Test phase then runs smoke and touched tests only, and the one full gate runs after
Archive on every run, whichever skill invoked it. multi-pr's pre-merge gate reuses that run when the
head is the gated commit, or that commit plus Handoff's two closing commits. Prose a model reads, so
this pins what text can show: each site names the fact, the Test phase keeps its ends, and the
chain-merge reuse rule keeps its limits.
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


def _flat(path: Path) -> str:
    return " ".join(_read(path).split())


@pytest.mark.parametrize("site", sorted(_SITES))
def test_every_site_names_the_fact(site: str) -> None:
    assert FACT in _read(_SITES[site]), f"{site} no longer names `{FACT}`"


# requirement: change-workflow / One full gate on every run, naming its commit
def test_the_test_phase_keeps_its_ends_and_names_the_commit() -> None:
    text = _read(_SITES["spec-to-pr Test"])
    para = text.split(f"**`{FACT}`.**", 1)[1].split("\n\n", 1)[0]
    for wanted in ("smoke and the touched tests only", "after Archive's push post-check", "orchestration-economy.md",
                   "on every run whichever skill or prompt invoked it", "names the commit it ran on",
                   "`ok` to `warn`", "The line absent"):
        assert wanted in para, f"the Full gate paragraph lost {wanted!r}"


# requirement: change-workflow / One full gate on every run, naming its commit
def test_no_caller_skip_is_left_in_the_shipped_skills() -> None:
    for path in _SKILLS.rglob("*.md"):
        text = _flat(path)
        assert "as its caller" not in text, f"{path} still tells spec-to-pr to skip for a caller"
        assert "as the caller" not in text, f"{path} still names a caller for the skip"


# requirement: change-workflow / One full gate on every run, naming its commit
def test_a_resume_runs_or_reports_the_full_gate() -> None:
    text = _read(_SITES["spec-to-pr Test"])
    resume = text.split("## Resume / dry-run", 1)[1]
    assert "A resume that reaches Handoff under `Full gate: final-commit-only`" in resume
    assert "runs the full gate first, or Handoff's Test row says it did not run and why" in resume


# requirement: change-workflow / One full gate on every run, naming its commit
def test_handoff_names_the_gated_commit() -> None:
    text = _flat(_SKILLS / "spec-to-pr" / "references" / "handoff.md")
    assert "`full gate: green on <sha>` or `full gate: red on <sha>`" in text
    assert "`full gate: skipped (<reason>)`" in text


# requirement: change-workflow / One full gate on every run, naming its commit
def test_multi_pr_reads_the_full_gate_line_before_recording_the_head() -> None:
    step = _flat(_SITES["multi-pr change loop"]).split("**Record the head, then read the Handoff report.**", 1)[1]
    step = step.split("Tier A", 1)[0]
    assert "first read the Handoff Test row's full-gate line" in step
    assert step.index("full-gate line") < step.index("then record this change")


# requirement: change-chains / An OpenSpec change chain merges only a later change's prerequisite, on the head it checked
def test_chain_merge_reuses_the_gate_only_on_the_gated_commit_or_the_two_handoff_commits() -> None:
    text = _flat(_SITES["chain-merge"])
    step = text.split("3. **The full Test gate is green on `head_sha`.**", 1)[1].split("4. **Remote checks", 1)[0]
    for wanted in (
        "`<gated>` equals `head_sha`",
        "lists only `docs: TODO.md` and `chore: spec-to-pr run log`, each at most once",
        "names only `TODO.md` and the run-log path Handoff stages",
        "void when the full gate may read `TODO.md`",
        "Unknown means run the gate",
        "A reused run that was red means do not merge, and do not run the gate again",
        "Any other case runs the gate here",
    ):
        assert wanted in step, f"chain-merge step 3 lost {wanted!r}"
    assert "the run `/cla:spec-to-pr` skipped" not in text
