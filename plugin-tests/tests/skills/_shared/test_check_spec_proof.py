"""Tests for check_spec_proof.py, the shipped requirement-to-proof checker.

Each test builds a throwaway git repo under tmp_path: a base commit on `main`,
then edits on top of it, so "changed since the merge-base" is a real git diff.
The marker strings the fixtures write are built as single-line f-strings so no
line of THIS file starts with a comment token followed by a marker, which the
checker (run read-only over the real repo) would otherwise read as a marker.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[4]
_SCRIPT = _REPO / ".claude" / "plugins" / "cla" / "skills" / "_shared" / "scripts" / "check_spec_proof.py"
_REAL_RUN = subprocess.run
_spec = importlib.util.spec_from_file_location("check_spec_proof", _SCRIPT)
csp = importlib.util.module_from_spec(_spec)
sys.modules["check_spec_proof"] = csp
_spec.loader.exec_module(csp)

FACTS = "cla.io/project-facts.md"
SPEC = "openspec/specs/alpha/spec.md"


def _spec_text(*reqs: tuple[str, str]) -> str:
    """A live spec: each req is (heading, body-with-scenarios)."""
    out = ["# alpha Specification", "", "## Purpose", "", "Something.", "", "## Requirements", ""]
    for heading, body in reqs:
        out += [f"### Requirement: {heading}", "", body, ""]
    return "\n".join(out)


def _delta_text(added: list[tuple[str, str]] = (), modified: list[tuple[str, str]] = ()) -> str:
    out = ["# Spec Delta", "", "## Purpose", "", "Something.", ""]
    for title, reqs in (("ADDED", added), ("MODIFIED", modified)):
        if reqs:
            out += [f"## {title} Requirements", ""]
            for heading, body in reqs:
                out += [f"### Requirement: {heading}", "", body, ""]
    return "\n".join(out)


def _scn(name: str, then: str = "it works") -> str:
    return f"#### Scenario: {name}\n\n- **WHEN** x\n- **THEN** {then}"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def _marker(kind: str, spec: str, heading: str) -> str:
    return f"# {kind}: {spec} / {heading}\ndef test_x():\n    pass\n"


@pytest.fixture
def repo(tmp_path: Path):
    """A repo whose base commit (branch main) holds one live spec with one proven requirement."""
    root = tmp_path / "r"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")
    _write(root, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case"))))
    _write(root, "tests/test_old.py", _marker("requirement", "alpha", "Old rule"))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    _git(root, "checkout", "-q", "-b", "feat")
    return root


def run(root: Path, capsys, *extra: str) -> tuple[int, str, str]:
    code = csp.main(["--root", str(root), "--base", "main", *extra])
    cap = capsys.readouterr()
    return code, cap.out, cap.err


NEW_REQ = ("New rule", "New SHALL.\n\n" + _scn("New case"))


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_new_requirement_with_no_proof_is_reported(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert "PROBLEM uncovered" in out and "alpha / New rule" in out
    assert "alpha / Old rule" not in out


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_marker_in_a_test_file_proves_it(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    _write(repo, "tests/test_new.py", _marker("requirement", "alpha", "New rule"))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "problems: 0" in out


# requirement: spec-proof / A checker reports requirements with no proof
def test_an_untracked_test_file_counts(repo, capsys):
    # Nothing is committed or added: a marker in a new file must still be read.
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    _write(repo, "tests/untracked.py", _marker("requirement", "alpha", "New rule"))
    assert run(repo, capsys)[0] == 0


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_manual_line_in_a_touched_change_proves_it(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    _write(repo, "openspec/changes/c1/tasks.md", "# Tasks\n\nmanual: New rule: needs a live run\n")
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "manual lines: 1" in out


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_manual_line_in_an_untouched_change_does_not_count(repo, capsys):
    # The change dir exists at the base, so the branch never touches it.
    _git(repo, "checkout", "-q", "main")
    _write(repo, "openspec/changes/c1/tasks.md", "# Tasks\n\nmanual: New rule: old note\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1 on main")
    _git(repo, "checkout", "-q", "-b", "feat2")
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "alpha / New rule" in out


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_manual_heading_containing_a_colon_is_matched(repo, capsys):
    heading = "Resume: partly done"
    # "Resume" is a prefix of the other heading, so only the longest match names the right one.
    _write(
        repo,
        SPEC,
        _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), ("Resume", "Short."), (heading, "SHALL.\n\n" + _scn("c"))),
    )
    _write(repo, "tests/test_short.py", _marker("requirement", "alpha", "Resume"))
    _write(repo, "openspec/changes/c1/tasks.md", f"- [x] 1.1 manual: {heading}: a reason\n")
    code, out, _ = run(repo, capsys)
    assert code == 0, out


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_pure_heading_rename_needs_no_new_proof(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule renamed", "Old SHALL.\n\n" + _scn("Old case"))))
    _write(repo, "tests/test_old.py", _marker("requirement", "alpha", "Old rule renamed"))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "changed requirements: 0" in out


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_changed_body_needs_proof_again(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL, now different.\n\n" + _scn("Old case"))))
    _write(repo, "tests/test_old.py", "")
    code, out, _ = run(repo, capsys)
    assert code == 1 and "alpha / Old rule" in out


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_changed_scenario_changes_its_requirement(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case", then="something else"))))
    _write(repo, "tests/test_old.py", "")
    assert run(repo, capsys)[0] == 1


# requirement: spec-proof / A checker reports requirements with no proof
def test_an_active_delta_is_checked_against_its_own_changes_tasks(repo, capsys):
    _write(repo, "openspec/changes/c1/specs/beta/spec.md", _delta_text(added=[NEW_REQ]))
    _write(repo, "openspec/changes/c2/tasks.md", "manual: New rule: elsewhere\n")
    code, out, _ = run(repo, capsys)
    assert code == 1 and "beta / New rule" in out
    _write(repo, "openspec/changes/c1/tasks.md", "manual: New rule: here\n")
    assert run(repo, capsys)[0] == 0


# requirement: spec-proof / A checker reports requirements with no proof
def test_only_added_and_modified_sections_of_a_delta_count(repo, capsys):
    text = _delta_text(added=[NEW_REQ]) + "\n## REMOVED Requirements\n\n### Requirement: Gone\n\nReason.\n"
    _write(repo, "openspec/changes/c1/specs/beta/spec.md", text)
    _write(repo, "openspec/changes/c1/tasks.md", "manual: New rule: ok\n")
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "Gone" not in out


# requirement: spec-proof / A checker reports requirements with no proof
def test_archiving_a_delta_unchanged_asks_for_no_new_proof(repo, capsys):
    _write(repo, "openspec/changes/c1/specs/beta/spec.md", _delta_text(added=[NEW_REQ]))
    _write(repo, "tests/test_new.py", _marker("requirement", "beta", "New rule"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "feat")
    _git(repo, "checkout", "-q", "-b", "arch")
    (repo / "openspec/changes/archive").mkdir()
    (repo / "openspec/changes/c1").rename(repo / "openspec/changes/archive/2026-01-01-c1")
    (repo / "tests/test_new.py").unlink()
    _write(repo, "openspec/specs/beta/spec.md", _spec_text(NEW_REQ))
    code, out, _ = run(repo, capsys)
    # The live spec is new on this branch and its marker is gone, so it is reported;
    # the moved delta text equals the active copy at the base and adds no demand.
    problems = [line for line in out.splitlines() if line.startswith("PROBLEM")]
    assert code == 1 and len(problems) == 1 and "openspec/specs/beta/spec.md" in problems[0]
    assert "archived delta 1" in out


# requirement: spec-proof / A checker reports requirements with no proof
def test_without_a_default_branch_the_changed_rule_is_off_and_said(tmp_path, capsys):
    root = tmp_path / "plain"
    _write(root, SPEC, _spec_text(NEW_REQ))
    code = csp.main(["--root", str(root)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "rule is off" in out


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_repo_with_no_commits_turns_the_rule_off_too(tmp_path, capsys):
    root = tmp_path / "fresh"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _write(root, SPEC, _spec_text(NEW_REQ))
    code = csp.main(["--root", str(root)])
    assert code == 0 and "rule is off" in capsys.readouterr().out


# requirement: spec-proof / A checker reports requirements with no proof
def test_the_script_runs_as_a_program_and_exits_nonzero(repo):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    r = subprocess.run([sys.executable, str(_SCRIPT), "--root", str(repo), "--base", "main"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1 and "PROBLEM uncovered" in r.stdout


# requirement: spec-proof / A checker reports requirements with no proof
def test_the_checker_edits_nothing(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    before = subprocess.run(["git", "status", "--porcelain", "--ignored", "-uall"], cwd=repo, capture_output=True, text=True).stdout
    run(repo, capsys)
    after = subprocess.run(["git", "status", "--porcelain", "--ignored", "-uall"], cwd=repo, capture_output=True, text=True).stdout
    assert before == after


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_dangling_marker_names_its_file(repo, capsys):
    _write(repo, "tests/test_bad.py", _marker("requirement", "alpha", "No such rule"))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert "PROBLEM dangling: tests/test_bad.py" in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_marker_naming_an_unknown_spec_dangles(repo, capsys):
    _write(repo, "tests/test_bad.py", _marker("requirement", "nope", "Old rule"))
    assert "PROBLEM dangling" in run(repo, capsys)[1]


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_marker_for_an_active_delta_requirement_is_live(repo, capsys):
    _write(repo, "openspec/changes/c1/specs/beta/spec.md", _delta_text(added=[NEW_REQ]))
    _write(repo, "tests/test_new.py", _marker("requirement", "beta", "New rule"))
    code, out, _ = run(repo, capsys)
    assert code == 0, out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_marker_naming_only_an_archived_requirement_dangles(repo, capsys):
    _write(repo, "openspec/changes/archive/2026-01-01-c0/specs/beta/spec.md", _delta_text(added=[("Gone rule", "Was SHALL.")]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "archived on main")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "feat")
    _git(repo, "checkout", "-q", "-b", "next")
    _write(repo, "tests/test_gone.py", _marker("requirement", "beta", "Gone rule"))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "PROBLEM dangling: tests/test_gone.py" in out


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_manual_line_in_a_change_the_branch_archives_proves_a_live_requirement(repo, capsys):
    _write(repo, "openspec/changes/c1/tasks.md", "manual: Live rule: needs a run\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "feat")
    _git(repo, "checkout", "-q", "-b", "arch")
    (repo / "openspec/changes/archive").mkdir()
    (repo / "openspec/changes/c1").rename(repo / "openspec/changes/archive/2026-01-01-c1")
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), ("Live rule", "New SHALL.")))
    code, out, _ = run(repo, capsys)
    assert code == 0, out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_marker_in_a_markdown_file_is_not_a_marker(repo, capsys):
    _write(repo, "docs/guide.md", _marker("requirement", "nope", "Nothing"))
    code, out, _ = run(repo, capsys)
    assert code == 0, out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_other_comment_tokens_are_read(repo, capsys):
    _write(repo, "web/a.js", "// requirement: nope / Nothing\n")
    _write(repo, "web/b.sql", "-- requirement: nope / Other\n")
    _write(repo, "web/c.css", "/* requirement: nope / Third */\n")
    out = run(repo, capsys)[1]
    assert out.count("PROBLEM dangling") == 3


# requirement: spec-proof / A checker reports proof that points at nothing
def test_tests_glob_limits_the_scan(repo, capsys):
    _write(repo, "other/test_bad.py", _marker("requirement", "alpha", "No such rule"))
    assert run(repo, capsys, "--tests", "tests/*")[0] == 0
    assert run(repo, capsys, "--tests", "other/*")[0] == 1


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_manual_line_naming_nothing_in_an_active_change_dangles(repo, capsys):
    _write(repo, "openspec/changes/c1/tasks.md", "manual: Made up: because\n")
    code, out, _ = run(repo, capsys)
    assert code == 1 and "PROBLEM dangling: openspec/changes/c1/tasks.md" in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_manual_line_in_an_archived_change_is_left_alone(repo, capsys):
    _write(repo, "openspec/changes/archive/2026-01-01-c0/tasks.md", "manual: Long gone: renamed since\n")
    assert run(repo, capsys)[0] == 0


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_template_placeholder_line_is_not_a_note(repo, capsys):
    _write(repo, "openspec/changes/c1/tasks.md", "manual: <heading>: <reason>\n")
    assert run(repo, capsys)[0] == 0


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_repeated_requirement_heading_is_reported(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "A."), ("Old rule", "B.")))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "PROBLEM repeated: openspec/specs/alpha/spec.md" in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_heading_repeated_across_added_and_modified_is_reported(repo, capsys):
    _write(repo, "openspec/changes/c1/specs/beta/spec.md", _delta_text(added=[NEW_REQ], modified=[NEW_REQ]))
    assert "PROBLEM repeated" in run(repo, capsys)[1]


# requirement: spec-proof / A checker reports proof that points at nothing
def test_headings_inside_a_code_fence_are_not_requirements(repo, capsys):
    body = "SHALL.\n\n```\n### Requirement: Fenced\n```\n"
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), ("Real", body)))
    _write(repo, "tests/test_r.py", _marker("requirement", "alpha", "Real"))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "Fenced" not in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_an_empty_corpus_exits_two(tmp_path, capsys):
    root = tmp_path / "empty"
    root.mkdir()
    code = csp.main(["--root", str(root)])
    err = capsys.readouterr().err
    assert code == 2 and "no spec files" in err


# requirement: spec-proof / A repo chooses proof per requirement or per scenario
def test_no_facts_line_means_requirement(repo, capsys):
    out = run(repo, capsys)[1]
    assert "granularity: requirement (default" in out


# requirement: spec-proof / A repo chooses proof per requirement or per scenario
def test_a_scenario_repo_reports_an_unproven_scenario(repo, capsys):
    _write(repo, FACTS, "# Facts\n\n- Test proof granularity: scenario\n")
    _write(repo, "tests/test_old.py", _marker("scenario", "alpha", "Old case"))
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case") + "\n\n" + _scn("Added case"))))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert "alpha / Added case" in out and "alpha / Old rule" not in out
    assert "granularity: scenario" in out


# requirement: spec-proof / A repo chooses proof per requirement or per scenario
def test_a_scenario_marker_proves_a_scenario_and_a_requirement_marker_is_the_wrong_kind(repo, capsys):
    _write(repo, FACTS, "- Test proof granularity: scenario\n")
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case") + "\n\n" + _scn("Added case"))))
    _write(repo, "tests/test_old.py", _marker("scenario", "alpha", "Old case") + _marker("scenario", "alpha", "Added case"))
    assert run(repo, capsys)[0] == 0
    _write(repo, "tests/test_wrong.py", _marker("requirement", "alpha", "Old rule"))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "this repo proves per scenario" in out


# requirement: spec-proof / A repo chooses proof per requirement or per scenario
def test_a_requirement_repo_rejects_the_retired_scenario_marker(repo, capsys):
    _write(repo, "tests/test_old2.py", _marker("scenario", "alpha", "Old case"))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "this repo proves per requirement" in out


# requirement: spec-proof / A repo chooses proof per requirement or per scenario
def test_a_repeated_scenario_heading_is_reported_in_scenario_mode(repo, capsys):
    _write(repo, FACTS, "- Test proof granularity: scenario\n")
    _write(repo, SPEC, _spec_text(("One", _scn("Same")), ("Two", _scn("Same", then="y"))))
    assert "PROBLEM repeated" in run(repo, capsys)[1]


@pytest.mark.parametrize(
    "line",
    [
        "- Test proof granularity: per-scenario",
        "- Test proof granularity: Scenario",
        "- Test proof granularity:",
        "* Test proof granularity: scenario",
        "- test proof granularity: scenario",
        "- **Test proof granularity**: scenario",
        "Test proof granularity: scenario",
        "- Test proof granularity: scenario # note",
    ],
)
# requirement: spec-proof / A repo chooses proof per requirement or per scenario
def test_a_malformed_facts_line_exits_two_and_names_it(repo, capsys, line):
    _write(repo, FACTS, f"# Facts\n\n{line}\n")
    code, out, err = run(repo, capsys)
    assert code == 2 and not out
    assert f"{FACTS}:3" in err and "requirement" in err and "scenario" in err


# requirement: spec-proof / A repo chooses proof per requirement or per scenario
def test_a_repeated_facts_line_exits_two(repo, capsys):
    _write(repo, FACTS, "- Test proof granularity: scenario\n- Test proof granularity: requirement\n")
    code, _, err = run(repo, capsys)
    assert code == 2 and "lines 1, 2" in err


# requirement: spec-proof / A repo chooses proof per requirement or per scenario
def test_prose_that_mentions_the_phrase_mid_line_is_not_the_fact(repo, capsys):
    _write(repo, FACTS, "The Test proof granularity fact is set below.\n\n- Test proof granularity: requirement\n")
    out = run(repo, capsys)[1]
    assert f"granularity: requirement ({FACTS}:3)" in out


# requirement: spec-proof / A repo chooses proof per requirement or per scenario
def test_this_repos_facts_line_and_cla_setup_agree_with_the_checker():
    mode, source = csp.read_granularity(_REPO)
    assert mode == "requirement" and source == f"{FACTS}:{_line_of(_REPO / FACTS)}"
    setup = (_REPO / ".claude" / "plugins" / "cla" / "skills" / "cla-setup" / "SKILL.md").read_text(encoding="utf-8")
    assert "`- Test proof granularity: requirement`" in setup and "`- Test proof granularity: scenario`" in setup


def _line_of(path: Path) -> int:
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("- Test proof granularity:"):
            return n
    raise AssertionError("no facts line")


# requirement: spec-proof / Half-proven and waiting requirements are counted apart
def test_a_prompt_half_with_a_marker_is_accepted_and_counted_apart(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    _write(repo, "tests/test_new.py", _marker("requirement", "alpha", "New rule"))
    _write(repo, "openspec/changes/c1/tasks.md", "manual: New rule: the skill step (prompt half)\n")
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "manual lines: 1 (prompt half: 1)" in out


# requirement: spec-proof / Half-proven and waiting requirements are counted apart
def test_a_prompt_half_without_a_marker_is_reported(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    _write(repo, "openspec/changes/c1/tasks.md", "manual: New rule: the skill step (prompt half)\n")
    code, out, _ = run(repo, capsys)
    assert code == 1 and "PROBLEM prompt-half" in out and "PROBLEM uncovered" not in out


# requirement: spec-proof / Half-proven and waiting requirements are counted apart
def test_a_waiting_line_covers_a_changed_requirement_and_is_counted(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    _write(repo, "openspec/changes/c1/tasks.md", "- [ ] 3.1 waiting: New rule: waiting on PR B (FIX 2)\n")
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "waiting lines: 1 (covering a changed requirement: 1)" in out


# requirement: spec-proof / Half-proven and waiting requirements are counted apart
def test_a_waiting_line_in_an_archived_change_is_reported(repo, capsys):
    _write(repo, "openspec/changes/archive/2026-01-01-c0/tasks.md", "waiting: Old rule: waiting on PR B\n")
    code, out, _ = run(repo, capsys)
    assert code == 1 and "PROBLEM waiting" in out and "archived but still waiting" in out


# requirement: spec-proof / Half-proven and waiting requirements are counted apart
def test_a_waiting_line_beside_a_proven_requirement_is_reported(repo, capsys):
    _write(repo, "openspec/changes/c1/tasks.md", "waiting: Old rule: waiting on PR B\n")
    code, out, _ = run(repo, capsys)
    assert code == 1 and "already proven" in out


# requirement: spec-proof / Half-proven and waiting requirements are counted apart
def test_a_waiting_line_for_an_unproven_requirement_is_not_reported_when_unchanged(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    _write(repo, "openspec/changes/c1/tasks.md", "waiting: New rule: later\n")
    out = run(repo, capsys)[1]
    assert "PROBLEM waiting" not in out


def test_counts_are_printed(repo, capsys):
    out = run(repo, capsys)[1]
    for label in ("granularity:", "specs:", "markers:", "manual lines:", "waiting lines:", "repo-wide coverage (information only): 1/1", "problems: 0"):
        assert label in out


def test_validate_is_skipped_and_said_when_the_cli_is_absent(repo, capsys, monkeypatch):
    monkeypatch.setattr(csp.shutil, "which", lambda name: None)
    code, out, _ = run(repo, capsys, "--validate")
    assert code == 0 and "validate: skipped" in out


def test_validate_failure_is_a_problem(repo, capsys, monkeypatch):
    monkeypatch.setattr(csp.shutil, "which", lambda name: sys.executable)
    monkeypatch.setattr(
        csp.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="bad spec\n", stderr="") if cmd[0] == sys.executable else _REAL_RUN(cmd, **kw),
    )
    code, out, _ = run(repo, capsys, "--validate")
    assert code == 1 and "PROBLEM validate" in out and "bad spec" in out
