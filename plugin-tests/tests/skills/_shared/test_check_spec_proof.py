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
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")


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
    _write(root, "tests/t.py", "x = 1")
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
    _write(root, "tests/t.py", "x = 1")
    code = csp.main(["--root", str(root)])
    assert code == 0 and "rule is off" in capsys.readouterr().out


# requirement: spec-proof / A checker reports requirements with no proof
def test_the_script_runs_as_a_program_and_exits_nonzero(repo):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    r = subprocess.run([sys.executable, str(_SCRIPT), "--root", str(repo), "--base", "main"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 1 and "PROBLEM uncovered" in r.stdout


# requirement: spec-proof / A checker reports requirements with no proof
def test_the_checker_edits_nothing(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    before = subprocess.run(["git", "status", "--porcelain", "--ignored", "-uall"], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    run(repo, capsys)
    after = subprocess.run(["git", "status", "--porcelain", "--ignored", "-uall"], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
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


# requirement: spec-proof / A checker reports requirements with no proof
def test_an_unresolvable_explicit_base_exits_two_not_zero(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ))
    code = csp.main(["--root", str(repo), "--base", "mian"])
    cap = capsys.readouterr()
    assert code == 2 and "mian" in cap.err and not cap.out


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_base_with_no_common_history_exits_two(repo, capsys):
    _git(repo, "checkout", "-q", "--orphan", "other")
    _write(repo, "z.txt", "z")
    _git(repo, "add", "z.txt")
    _git(repo, "commit", "-q", "-m", "unrelated")
    _git(repo, "checkout", "-q", "feat")
    code = csp.main(["--root", str(repo), "--base", "other"])
    assert code == 2 and "merge-base" in capsys.readouterr().err


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_root_below_the_repo_top_still_compares_with_the_base(repo, capsys):
    sub = repo / "pkg"
    _write(repo, "pkg/" + SPEC, _spec_text(("Old rule", "Old SHALL.")))
    _write(repo, "pkg/tests/t.py", "x = 1")  # Old rule carries no marker: only an unchanged verdict spares it
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "pkg")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "feat")
    _git(repo, "checkout", "-q", "-b", "feat3")
    _write(repo, "pkg/" + SPEC, _spec_text(("Old rule", "Old SHALL."), NEW_REQ))
    code = csp.main(["--root", str(sub), "--base", "main"])
    out = capsys.readouterr().out
    assert code == 1 and "alpha / New rule" in out and "alpha / Old rule" not in out
    # A COMMITTED tasks.md is only seen through `git diff`, whose paths must be relative to the root.
    _write(repo, "pkg/openspec/changes/c1/tasks.md", "manual: New rule: ok\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "tasks")
    assert csp.main(["--root", str(sub), "--base", "main"]) == 0, capsys.readouterr().out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_specs_that_parse_to_nothing_exit_two(repo, capsys):
    _write(repo, SPEC, "# alpha\n\n## Purpose\n\nx\n\n## Notes\n\n### Requirement: Hidden\n\nSHALL.\n")
    code = csp.main(["--root", str(repo), "--base", "main"])
    assert code == 2 and "no requirement parsed" in capsys.readouterr().err


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_requirements_heading_with_a_suffix_is_still_read(repo, capsys):
    text = _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), NEW_REQ).replace("## Requirements", "## Requirements (v2)")
    _write(repo, SPEC, text)
    assert "alpha / New rule" in run(repo, capsys)[1]


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_test_file_in_another_encoding_is_still_scanned(repo, capsys):
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "test_latin.py").write_bytes("# caf\xe9\n# requirement: alpha / No such rule\n".encode("latin-1"))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "PROBLEM dangling: tests/test_latin.py" in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_binary_file_is_skipped_and_named(repo, capsys):
    (repo / "tests" / "blob.dat").write_bytes(b"\0\1\2# requirement: alpha / X\n")
    code, out, _ = run(repo, capsys)
    assert code == 0 and "skipped 1 binary: tests/blob.dat" in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_tests_glob_that_matches_nothing_exits_two(repo, capsys):
    code, _, err = run(repo, capsys, "--tests", "nope/*")
    assert code == 2 and "matched nothing" in err


# requirement: spec-proof / A checker reports proof that points at nothing
@pytest.mark.parametrize("line", ["# requirement: Alpha / Old rule", "# requirement: alpha/Old rule", "# requirement: my_spec / Old rule"])
def test_a_marker_that_misses_the_format_is_reported_not_dropped(repo, capsys, line):
    _write(repo, "tests/test_bad.py", line + "\n")
    code, out, _ = run(repo, capsys)
    assert code == 1 and "looks like a marker" in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_repeat_inside_an_archived_delta_is_not_reported(repo, capsys):
    _write(repo, FACTS, "- Test proof granularity: scenario\n")
    _write(repo, "tests/test_old.py", _marker("scenario", "alpha", "Old case"))
    _write(repo, "openspec/changes/archive/2026-01-01-c0/specs/beta/spec.md", _delta_text(added=[("A", _scn("Same")), ("B", _scn("Same"))]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "archived with a repeat")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "feat")
    _git(repo, "checkout", "-q", "-b", "next")
    code, out, _ = run(repo, capsys)
    assert code == 0, out


# requirement: spec-proof / A repo chooses proof per requirement or per scenario
def test_a_byte_order_mark_does_not_hide_the_facts_line(repo, capsys):
    (repo / "cla.io").mkdir()
    (repo / FACTS).write_bytes(b"\xef\xbb\xbf- Test proof granularity: scenario\n")
    assert "granularity: scenario" in run(repo, capsys)[1]


# requirement: spec-proof / A repo chooses proof per requirement or per scenario
@pytest.mark.parametrize("line", ["1. Test proof granularity: scenario", "> - Test proof granularity: scenario"])
def test_a_numbered_or_quoted_facts_line_is_malformed(repo, capsys, line):
    _write(repo, FACTS, line + "\n")
    assert run(repo, capsys)[0] == 2


def test_an_unexpected_crash_exits_two_not_one(repo, capsys, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(csp, "check", boom)
    code, _, err = run(repo, capsys)
    assert code == 2 and "RuntimeError" in err


CONFIG = "openspec/config.yaml"


def _config(root: Path, chars: str = "500 characters or fewer", scn: str = "at most 3 scenarios", reqs: str = "at most 8 requirements") -> None:
    rule = "Write each requirement as one sentence of " + chars + ", with " + scn + ". A spec holds " + reqs + "."
    _write(
        root,
        CONFIG,
        "schema: spec-driven\n\nrules:\n  proposal:\n    - Keep it short, at most 2 scenarios of prose.\n  specs:\n    - \""
        + rule
        + "\"\n    - Another rule.\n  tasks:\n    - Keep tasks at most 99 requirements long.\n",
    )


def _fmt(root: Path, capsys) -> tuple[int, str]:
    code, out, _ = run(root, capsys)
    return code, "\n".join(line for line in out.splitlines() if line.startswith("PROBLEM format"))


FOUR = ("Four", "SHALL.\n\n" + "\n\n".join(_scn(f"S{i}", then=f"t{i}") for i in range(4)))


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_a_requirement_with_too_many_scenarios_is_reported(repo, capsys):
    _config(repo)
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), FOUR))
    _write(repo, "tests/test_four.py", _marker("requirement", "alpha", "Four"))
    code, fmt = _fmt(repo, capsys)
    assert code == 1 and "alpha/spec.md" in fmt and "'Four' has 4 scenarios, the limit is 3" in fmt


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_a_repo_with_different_limits_is_held_to_its_own(repo, capsys):
    _config(repo, scn="at most 5 scenarios")
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), FOUR))
    _write(repo, "tests/test_four.py", _marker("requirement", "alpha", "Four"))
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "scenarios 5" in out


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_a_long_statement_is_reported_and_scenario_text_does_not_count(repo, capsys):
    _config(repo, chars="80 characters or fewer")
    long_stmt = "word " * 30
    ok = ("Fine", "Short SHALL.\n\n" + _scn("A", then="x " * 100))
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), ("Long", long_stmt + "\n\n" + _scn("B")), ok))
    _write(repo, "tests/test_m.py", _marker("requirement", "alpha", "Long") + _marker("requirement", "alpha", "Fine"))
    code, fmt = _fmt(repo, capsys)
    assert code == 1 and "'Long' states 149 characters" in fmt and "'Fine'" not in fmt


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_a_spec_with_too_many_requirements_is_reported(repo, capsys):
    _config(repo, reqs="at most 2 requirements")
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), ("Two", "B."), ("Three", "C.")))
    _write(repo, "tests/test_m.py", _marker("requirement", "alpha", "Two") + _marker("requirement", "alpha", "Three"))
    code, fmt = _fmt(repo, capsys)
    assert code == 1 and "3 requirements, the limit is 2" in fmt


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_a_delta_is_held_to_the_requirement_limits_but_an_archived_delta_is_not(repo, capsys):
    _config(repo)
    _write(repo, "openspec/changes/c1/specs/beta/spec.md", _delta_text(added=[FOUR]))
    _write(repo, "openspec/changes/archive/2026-01-01-c0/specs/beta/spec.md", _delta_text(added=[FOUR]))
    _write(repo, "openspec/changes/c1/tasks.md", "manual: Four: ok\n")
    code, fmt = _fmt(repo, capsys)
    assert "openspec/changes/c1/specs/beta/spec.md" in fmt and "archive" not in fmt


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_a_limit_the_config_does_not_state_is_not_enforced_and_is_named(repo, capsys):
    _config(repo, reqs="a modest number of requirements")
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), FOUR))
    _write(repo, "tests/test_four.py", _marker("requirement", "alpha", "Four"))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "has 4 scenarios" in out
    assert "not enforced, not found: requirements" in out


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_no_config_means_no_limits_and_the_output_says_so(repo, capsys):
    code, out, _ = run(repo, capsys)
    assert code == 0, out
    assert "not enforced, not found: chars, scenarios, requirements" in out


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_limits_come_from_the_specs_rules_only(repo):
    # The fixture's proposal and tasks groups use the same words with other numbers.
    _config(repo)
    limits, missing = csp.read_format_limits(repo)
    assert limits == {"chars": 500, "scenarios": 3, "requirements": 8} and not missing


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_this_repos_config_states_all_three_limits_and_its_specs_meet_them():
    limits, missing = csp.read_format_limits(_REPO)
    assert set(limits) == {"chars", "scenarios", "requirements"} and not missing
    files = csp._spec_files(_REPO, "requirement")
    assert csp.check_format(files, limits) == []


# requirement: spec-proof / A checker reports proof that points at nothing
def test_prose_that_starts_like_a_marker_is_not_one(repo, capsys):
    prose = "# scenario: empty input returns []\n// requirement: must be positive\n * scenario: user not logged in\n"
    _write(repo, "tests/test_prose.py", prose + "# requirement: <spec> / <heading>\n")
    code, out, _ = run(repo, capsys)
    assert code == 0, out


# requirement: spec-proof / A checker reports proof that points at nothing
@pytest.mark.parametrize(
    "line",
    ["<!-- requirement: Alpha / Old rule -->", "# Requirement: alpha / Old rule", "# requirement:alpha/Old rule", "<!-- requirement: alpha/Rejects <empty> input -->"],
)
def test_near_miss_markers_including_html_comments_are_reported(repo, capsys, line):
    _write(repo, "web/page.html", line + "\n")
    code, out, _ = run(repo, capsys)
    assert code == 1 and "looks like a marker" in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_utf16_test_file_is_scanned_not_skipped(repo, capsys):
    (repo / "tests" / "t.ps1").write_bytes("# requirement: alpha / No such rule\r\n".encode("utf-16"))
    code, out, _ = run(repo, capsys)
    assert code == 1 and "PROBLEM dangling: tests/t.ps1" in out and "skipped" not in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_repo_git_refuses_is_an_error_not_a_non_repo(tmp_path, capsys):
    root = tmp_path / "broken"
    _write(root, SPEC, _spec_text(NEW_REQ))
    _write(root, "tests/t.py", "x = 1")
    (root / ".git").mkdir()  # git cannot read this, as with a dubious-ownership refusal
    code = csp.main(["--root", str(root)])
    assert code == 2 and "git refused" in capsys.readouterr().err


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_delta_with_requirements_under_no_delta_heading_is_reported(repo, capsys):
    text = "# Spec Delta\n\n## Requirements\n\n### Requirement: Lost\n\nSHALL.\n"
    _write(repo, "openspec/changes/c1/specs/beta/spec.md", text)
    code, out, _ = run(repo, capsys)
    assert code == 1 and "PROBLEM empty: openspec/changes/c1/specs/beta/spec.md" in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_removed_only_delta_is_not_empty(repo, capsys):
    _write(repo, "openspec/changes/c1/specs/beta/spec.md", "## REMOVED Requirements\n\n### Requirement: Gone\n\n**Migration**: x\n")
    code, out, _ = run(repo, capsys)
    assert code == 0, out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_live_spec_with_no_unit_is_reported_even_when_others_parse(repo, capsys):
    _write(repo, "openspec/specs/beta/spec.md", "# beta\n\n## Notes\n\n### Requirement: Hidden\n\nSHALL.\n")
    code, out, _ = run(repo, capsys)
    assert code == 1 and "PROBLEM empty: openspec/specs/beta/spec.md" in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_archived_deltas_alone_do_not_satisfy_the_corpus_check(tmp_path, capsys):
    root = tmp_path / "arch"
    _write(root, "openspec/changes/archive/2026-01-01-c0/specs/beta/spec.md", _delta_text(added=[NEW_REQ]))
    _write(root, "tests/t.py", "x = 1")
    code = csp.main(["--root", str(root)])
    assert code == 2 and "live spec or active delta" in capsys.readouterr().err


# requirement: spec-proof / A checker reports requirements with no proof
def test_a_fetched_origin_with_no_local_commit_turns_the_rule_off(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main")
    _git(src, "config", "user.email", "t@example.com")
    _git(src, "config", "user.name", "t")
    _git(src, "config", "commit.gpgsign", "false")
    _write(src, "a.txt", "a")
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "a")
    root = tmp_path / "unborn"
    root.mkdir()
    _git(root, "init", "-q", "-b", "work")
    _git(root, "remote", "add", "origin", str(src))
    _git(root, "fetch", "-q", "origin")
    _write(root, SPEC, _spec_text(NEW_REQ))
    _write(root, "tests/t.py", "x = 1")
    code = csp.main(["--root", str(root)])
    assert code == 0 and "no commit on HEAD yet" in capsys.readouterr().out


def test_a_crash_prints_its_traceback(repo, capsys, monkeypatch):
    monkeypatch.setattr(csp, "check", lambda *a, **k: 1 / 0)
    code, _, err = run(repo, capsys)
    assert code == 2 and "Traceback" in err and "ZeroDivisionError" in err


def _raw_config(root: Path, text: str) -> None:
    _write(root, CONFIG, text)


_RULE = "Each requirement is one sentence of 500 characters or fewer with at most 3 scenarios, and a spec holds at most 8 requirements."


# requirement: spec-proof / A checker reports specs over the repo's format limits
@pytest.mark.parametrize(
    "text",
    [
        f"rules:\n  specs:\n  - \"{_RULE}\"\n",  # list items at the key's own indent
        f"rules:\n    specs:\n      - \"{_RULE}\"\n",  # four-space indent
        f"rules:\n  specs: |\n    {_RULE}\n",  # block scalar
        f"rules:\n  specs:  # format\n    - \"{_RULE}\"\n",
        f"other:\n  specs:\n    - x\nrules:\n  specs:\n    - \"{_RULE}\"\n",  # an earlier `specs:` under another key
        f"rules:\n  specs:\n    - \"At most 3 scenarios, 500 characters or less, no more than 8 requirements.\"\n",
        f"rules:\r\n  specs:\r\n    - \"{_RULE}\"\r\n",
    ],
)
def test_the_limits_are_read_from_any_valid_layout_of_rules_specs(repo, text):
    _raw_config(repo, text)
    assert csp.read_format_limits(repo) == ({"chars": 500, "scenarios": 3, "requirements": 8}, [])


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_a_yml_config_is_read_too(repo):
    _write(repo, "openspec/config.yml", f"rules:\n  specs:\n    - \"{_RULE}\"\n")
    assert csp.read_format_limits(repo)[0]["scenarios"] == 3


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_rules_without_a_specs_group_state_no_limits(repo):
    _raw_config(repo, "rules:\n  tasks:\n    - at most 3 scenarios\n")
    assert csp.read_format_limits(repo) == ({}, ["chars", "scenarios", "requirements"])


# requirement: spec-proof / A checker reports specs over the repo's format limits
@pytest.mark.parametrize("sentence", ["Keep it plain.", "Each spec holds a modest number of requirements."])
def test_a_specs_group_that_states_no_limit_is_an_error(repo, capsys, sentence):
    _raw_config(repo, f"rules:\n  specs:\n    - \"{sentence}\"\n")
    code = csp.main(["--root", str(repo), "--base", "main"])
    assert code == 2 and "states none of the format limits" in capsys.readouterr().err


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_a_limit_given_in_words_the_reader_does_not_know_is_an_error(repo, capsys):
    _raw_config(repo, "rules:\n  specs:\n    - \"500 characters or fewer, at most three scenarios, at most 8 requirements.\"\n")
    code = csp.main(["--root", str(repo), "--base", "main"])
    assert code == 2 and "scenarios in wording" in capsys.readouterr().err


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_a_delta_is_counted_with_the_live_spec_it_will_join(repo, capsys):
    _config(repo, reqs="at most 2 requirements")
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), ("Second", "B.")))
    _write(repo, "tests/test_m.py", _marker("requirement", "alpha", "Second"))
    _write(repo, "openspec/changes/c1/specs/alpha/spec.md", _delta_text(added=[NEW_REQ]))
    _write(repo, "tests/test_n.py", _marker("requirement", "alpha", "New rule"))
    code, fmt = _fmt(repo, capsys)
    assert code == 1 and "openspec/changes/c1/specs/alpha/spec.md: 3 requirements" in fmt
    removal = "\n## REMOVED Requirements\n\n### Requirement: Second\n\n**Migration**: x\n"
    _write(repo, "openspec/changes/c1/specs/alpha/spec.md", _delta_text(added=[NEW_REQ]) + removal)
    assert _fmt(repo, capsys)[1] == ""
    # A requirement the delta only MODIFIES does not grow the spec.
    _write(repo, "openspec/changes/c1/specs/alpha/spec.md", _delta_text(modified=[("Second", "B, changed.")]))
    assert _fmt(repo, capsys)[1] == ""


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_a_fence_in_a_statement_does_not_end_it_and_a_subsection_does(repo, capsys):
    _config(repo, chars="60 characters or fewer")
    fenced = "word " * 8 + "\n\n```\n#### Scenario: not one\n```\n\n" + "more " * 10 + "\n\n" + _scn("Real")
    notes = "short.\n\n#### Notes\n\n" + "long " * 40 + "\n\n" + _scn("Real")
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), ("Fenced", fenced), ("Notes", notes)))
    _write(repo, "tests/test_m.py", _marker("requirement", "alpha", "Fenced") + _marker("requirement", "alpha", "Notes"))
    code, fmt = _fmt(repo, capsys)
    assert "'Fenced' states" in fmt and "'Notes'" not in fmt


# requirement: spec-proof / A checker reports proof that points at nothing
def test_an_oversize_file_is_a_problem_not_a_quiet_skip(repo, capsys, monkeypatch):
    monkeypatch.setattr(csp, "_MAX_BYTES", 100)
    _write(repo, "tests/big.py", "# requirement: alpha / No such rule\n" + "x = 1\n" * 20)
    code, out, _ = run(repo, capsys)
    assert code == 1 and "PROBLEM unchecked: tests/big.py" in out


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_a_statement_exactly_at_the_limit_passes_and_one_over_is_reported(repo, capsys):
    _config(repo, chars="80 characters or fewer")
    at_limit = ("At limit", "a" * 80 + "\n\n" + _scn("A"))
    over = ("Over", "a" * 81 + "\n\n" + _scn("B"))
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), at_limit, over))
    _write(repo, "tests/test_m.py", _marker("requirement", "alpha", "At limit") + _marker("requirement", "alpha", "Over"))
    code, fmt = _fmt(repo, capsys)
    assert "'Over' states 81" in fmt and "'At limit'" not in fmt


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_a_spec_with_exactly_the_allowed_requirements_passes(repo, capsys):
    _config(repo, reqs="at most 2 requirements")
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), ("Second", "B.")))
    _write(repo, "tests/test_m.py", _marker("requirement", "alpha", "Second"))
    assert _fmt(repo, capsys) == (0, "")


# requirement: spec-proof / A checker reports specs over the repo's format limits
def test_exactly_the_allowed_scenarios_pass(repo, capsys):
    _config(repo, scn="at most 4 scenarios")
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), FOUR))
    _write(repo, "tests/test_four.py", _marker("requirement", "alpha", "Four"))
    assert _fmt(repo, capsys) == (0, "")


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_git_refused_working_directory_is_an_error_when_no_root_is_given(tmp_path, capsys, monkeypatch):
    root = tmp_path / "broken2"
    _write(root, SPEC, _spec_text(NEW_REQ))
    (root / ".git").mkdir()
    monkeypatch.chdir(root)
    code = csp.main([])
    assert code == 2 and "git refused" in capsys.readouterr().err


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_requirement_with_no_scenario_is_reported_in_scenario_mode(repo, capsys):
    _write(repo, FACTS, "- Test proof granularity: scenario\n")
    _write(repo, "tests/test_old.py", _marker("scenario", "alpha", "Old case"))
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), ("Bare", "Bare SHALL.")))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert f"PROBLEM empty: {SPEC}: requirement 'Bare' has no '#### Scenario:' heading" in out
    assert "'Old rule'" not in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_live_spec_with_only_a_bare_requirement_gets_one_empty_line_in_scenario_mode(repo, capsys):
    _write(repo, FACTS, "- Test proof granularity: scenario\n")
    _write(repo, "tests/test_old.py", _marker("scenario", "beta", "Old case"))
    _write(repo, "openspec/specs/beta/spec.md", _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case"))))
    _write(repo, SPEC, _spec_text(("Bare", "Bare SHALL.")))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert [l for l in out.splitlines() if f"PROBLEM empty: {SPEC}" in l] == [
        f"PROBLEM empty: {SPEC}: a live spec with no scenario parsed"
    ]


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_scenario_free_requirement_is_fine_in_requirement_mode(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n" + _scn("Old case")), ("Bare", "Bare SHALL.")))
    _write(repo, "tests/test_bare.py", _marker("requirement", "alpha", "Bare"))
    assert run(repo, capsys)[0] == 0


# requirement: spec-proof / A checker reports proof that points at nothing
def test_an_unclosed_code_fence_is_reported_per_file(repo, capsys):
    _write(repo, "openspec/specs/beta/spec.md", _spec_text(("Cut", "SHALL.\n\n```\nnever closed\n\n### Requirement: Hidden\n\nSHALL.")))
    code, out, _ = run(repo, capsys)
    assert code == 1
    assert "PROBLEM fence: openspec/specs/beta/spec.md" in out
    assert "PROBLEM fence: " + SPEC not in out


# requirement: spec-proof / A checker reports proof that points at nothing
def test_a_closed_code_fence_is_not_reported(repo, capsys):
    _write(repo, SPEC, _spec_text(("Old rule", "Old SHALL.\n\n```\nx\n```\n\n" + _scn("Old case"))))
    assert "PROBLEM fence" not in run(repo, capsys)[1]
