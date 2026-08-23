"""Claims, links and coverage over an OpenSpec change.

Nearly every case here is a defect the model actually shipped and a sweep over
355 real changes caught. They are written as behaviour rather than as regression
notes, but the reason each one exists is stated where it is not obvious — a
threshold with no recorded reason is a threshold the next person will "simplify".
"""
import pytest

import openspec_change as OC


PROPOSAL = """# Proposal: demo

## Why

Because.

## What Changes

- Delete `src/legacy/sync-engine/` entirely, including its `pyproject.toml`
  - a sub-bullet elaborating the one above
- Rewrite `conformance-checks/tests/test_no_project_tokens.py` and drop `EXEMPT_SKILLS`
- A warm-ink palette with a single amber accent and restrained typography

## Capabilities

### Modified Capabilities

- `cla-plugin`: the sync requirements go away

## Impact

- Consumers stop receiving updates
"""

TASKS = """# Tasks: demo

## 1. Delete

- [x] 1.1 Remove `src/legacy/sync-engine/` via `git rm -r`
- [x] 1.2 Delete the lockfile, updating `pyproject.toml`

## 2. Tests

- [ ] 2.1 In `conformance-checks/tests/test_no_project_tokens.py`, drop `EXEMPT_SKILLS`
"""

DESIGN = """# Design: demo

## Context

Words.

## Goals / Non-Goals

- Exactly one distribution route

## Decisions

1. **Delete outright, not deprecate.** A banner keeps dead code alive.
2. **Keep the overlay convention.** It survives without an engine.
"""

SPEC = """# Delta: cla-plugin — demo

## MODIFIED Requirements

### Requirement: Project-data scaffolding

Text.

## REMOVED Requirements

### Requirement: Sync provenance lockfile

Text.
"""

TEXTS = {"proposal": PROPOSAL, "design": DESIGN, "tasks": TASKS, "spec-cla-plugin": SPEC}


@pytest.fixture
def model():
    return OC.build("demo", TEXTS)


def kinds(model, kind):
    return [c for c in model["claims"] if c["kind"] == kind]


# ---------------------------------------------------------------- parsing


def test_promises_come_from_what_changes_only(model):
    got = [c["text"] for c in kinds(model, "promise")]
    assert len(got) == 3
    assert not any("Consumers stop receiving" in t for t in got)   # that is Impact
    assert not any("sync requirements" in t for t in got)          # that is Capabilities


def test_a_sub_bullet_is_not_its_own_promise(model):
    # It elaborates its parent. Counted separately, the parent reads as covered
    # while the detail nothing implements goes unmentioned.
    assert not any("sub-bullet" in c["text"] for c in kinds(model, "promise"))


def test_tasks_carry_their_number_and_checkbox_state(model):
    tasks = {c["num"]: c for c in kinds(model, "task")}
    assert set(tasks) == {"1.1", "1.2", "2.1"}
    assert tasks["1.1"]["done"] is True and tasks["2.1"]["done"] is False
    assert tasks["1.1"]["group"] == "1. Delete"


def test_requirements_carry_their_added_modified_removed_group(model):
    reqs = {c["text"]: c["group"] for c in kinds(model, "requirement")}
    assert reqs == {"Project-data scaffolding": "MODIFIED",
                    "Sync provenance lockfile": "REMOVED"}


def test_decisions_take_the_bold_lead_as_their_title(model):
    ds = {c["num"]: c["text"] for c in kinds(model, "decision")}
    assert ds["1"] == "Delete outright, not deprecate."
    assert "banner keeps dead code" in [c for c in kinds(model, "decision")
                                        if c["num"] == "1"][0]["body"]


def test_capabilities_are_read_with_their_new_or_modified_flag(model):
    caps = model["capabilities"]
    assert len(caps) == 1
    assert caps[0]["name"] == "cla-plugin" and caps[0]["new"] is False
    assert caps[0]["text"] == "cla-plugin: the sync requirements go away"
    # The line is asserted against the source rather than a hand-counted number,
    # which is wrong the moment the fixture gains a paragraph.
    assert PROPOSAL.split("\n")[caps[0]["line"] - 1].startswith("- `cla-plugin`")


def test_inline_markers_are_stripped_so_claims_match_rendered_text(model):
    p = kinds(model, "promise")[0]
    assert "`" not in p["text"] and "**" not in p["text"]


# ---------------------------------------------------------------- tokens


def test_a_directory_path_is_a_token():
    # Requiring a file extension missed `src/legacy/sync-engine/`
    # and let the generic `pyproject.toml` stand in for it.
    toks = OC.tokens_of({"raw": "Delete `src/legacy/sync-engine/` now"})
    assert "src/legacy/sync-engine/" in toks


def test_a_generic_filename_alone_is_not_evidence():
    # The same string names a different file in every directory, so two claims
    # sharing it are not talking about the same thing.
    assert OC.tokens_of({"raw": "update `pyproject.toml` and `SKILL.md`"}) == set()


def test_a_generic_filename_inside_a_path_is_still_evidence():
    toks = OC.tokens_of({"raw": "edit `skills/annotate/SKILL.md`"})
    assert "skills/annotate/skill.md" in toks


def test_a_short_identifier_is_not_evidence():
    # `cla-init` is eight characters and names a skill mentioned repo-wide;
    # matching on it reported a bullet as covered because the bullet LISTED it.
    assert OC.tokens_of({"raw": "the `cla-init` skill"}) == set()
    assert "exempt_skills" in OC.tokens_of({"raw": "drop `EXEMPT_SKILLS`"})


# ---------------------------------------------------------------- links


def test_a_shared_path_links_a_promise_to_its_task(model):
    p = [c for c in kinds(model, "promise") if "sync-engine" in c["text"]][0]
    pairs = [l for l in model["links"]
             if p["id"] in (l["src"], l["dst"]) and "tasks:1.1" in (l["src"], l["dst"])]
    assert len(pairs) == 1
    assert pairs[0]["kind"] == "path"


def test_the_most_specific_token_is_the_one_shown(model):
    """Two claims usually share several tokens and the page shows one reason.
    Keeping whichever arrived first showed `skill.md` where the evidence was a
    full directory path."""
    p = [c for c in kinds(model, "promise") if "sync-engine" in c["text"]][0]
    link = [l for l in model["links"]
            if {l["src"], l["dst"]} == {p["id"], "tasks:1.1"}][0]
    assert link["why"] == "src/legacy/sync-engine/"


def test_a_weaker_reason_already_recorded_is_upgraded_by_a_stronger_one():
    """The case the test above does NOT reach: it shares one token, so the
    upgrade never runs and it passes whether or not the upgrade exists — a
    mutation run is what showed that. Here the identifier sorts first and is
    recorded first, so only an upgrade can put the path in its place."""
    shared_id, shared_path = "`aaa_shared_identifier`", "`zzz/deep/dir/thing.py`"
    prop = ("# P\n\n## What Changes\n\n- Rework %s inside %s\n"
            % (shared_id, shared_path))
    tasks = "# T\n\n## 1. Go\n\n- [x] 1.1 Edit %s in %s\n" % (shared_id, shared_path)
    m = OC.build("demo", {"proposal": prop, "tasks": tasks})
    link = [l for l in m["links"] if {l["src"], l["dst"]} == {"proposal:p1", "tasks:1.1"}][0]
    assert link["kind"] == "path"
    assert link["why"] == "zzz/deep/dir/thing.py"


# ---------------------------------------------------------------- coverage


def test_only_a_path_or_a_citation_discharges_a_promise():
    """A bullet can MENTION a name without being about it. The sweep bullet in
    this repo's own change lists `sync-context` among its candidates and was
    read as implemented by every task touching that skill."""
    prop = ("# P\n\n## What Changes\n\n"
            "- Sweep for leftovers (candidates: `report-upstream`, `sync-context`)\n")
    tasks = "# T\n\n## 1. Go\n\n- [x] 1.1 Rewrite `sync-context` references\n"
    m = OC.build("demo", {"proposal": prop, "tasks": tasks})
    assert m["coverage"]["covered"] == []
    row = m["coverage"]["uncovered"][0]
    assert "weaker match" in row["why"]
    assert row["pays"], "the weak link is still shown, just not counted"


def test_a_promise_with_nothing_to_match_on_is_not_called_uncovered(model):
    """Half of all promises across 355 real changes name no file and no
    identifier. Calling them uncovered is the overclaim the tab exists to
    avoid: the detector has no basis to speak."""
    unchecked = [r["claim"]["text"] for r in model["coverage"]["unchecked"]]
    assert any("warm-ink palette" in t for t in unchecked)
    assert not any("warm-ink palette" in r["claim"]["text"]
                   for r in model["coverage"]["uncovered"])
    assert "no file path or identifier" in model["coverage"]["unchecked"][0]["why"]


def test_an_undone_task_is_its_own_bucket_not_an_uncovered_claim(model):
    """Mixing the two made every summary report one number for two different
    things: an unstarted change with 18 tasks read as "18 uncovered", which is
    the overclaim this module exists to prevent."""
    assert not [r for r in model["coverage"]["uncovered"] if r["claim"]["kind"] == "task"]
    rows = model["coverage"]["undone"]
    assert len(rows) == 1 and rows[0]["claim"]["num"] == "2.1"
    # The denominator is what stops this reading as an alarm in an in-flight
    # change, where most tasks being open is the normal state.
    assert "2 of 3 tasks done" in rows[0]["why"]


def test_requirements_are_never_counted_as_uncovered(model):
    """Requiring a task per requirement reported ten of eleven as uncovered on
    this repo's own change — formally true, and it buried the two real findings."""
    assert not [r for r in model["coverage"]["uncovered"]
                if r["claim"]["kind"] == "requirement"]
    assert not [r for r in model["coverage"]["unchecked"]
                if r["claim"]["kind"] == "requirement"]


def test_impacts_and_goals_are_context_never_owed(model):
    owed = {r["claim"]["kind"] for r in
            model["coverage"]["uncovered"] + model["coverage"]["unchecked"]}
    assert owed <= {"promise", "task"}


def test_capability_coverage_flags_a_delta_with_no_proposal_bullet(model):
    rows = {r["name"]: r for r in model["coverage"]["capabilities"]}
    assert rows["cla-plugin"]["named"] and rows["cla-plugin"]["delta"]
    assert rows["cla-plugin"]["why"] == ""


def test_capability_coverage_flags_a_named_capability_with_no_delta():
    m = OC.build("demo", {"proposal": PROPOSAL, "tasks": TASKS})
    row = m["coverage"]["capabilities"][0]
    assert row["named"] and not row["delta"]
    assert "no specs/cla-plugin/spec.md" in row["why"]


def test_stats_report_what_was_read(model):
    st = model["coverage"]["stats"]
    assert st["files"] == 4 and st["promises"] == 3
    assert st["tasks"] == 3 and st["tasks_done"] == 2


# ---------------------------------------------------------------- discovery


def test_a_change_is_found_by_bare_id_under_the_archive(tmp_path):
    d = tmp_path / "openspec" / "changes" / "archive" / "2026-08-13-remove-thing"
    d.mkdir(parents=True)
    (d / "proposal.md").write_text("# P\n", encoding="utf-8")
    # An archived change is prefixed with its date, so the id the author
    # remembers is not the directory name.
    assert OC.find_change("remove-thing", str(tmp_path)) == str(d)
    assert OC.find_change("nope", str(tmp_path)) is None


def test_files_come_back_in_the_fixed_order(tmp_path):
    d = tmp_path / "c"
    (d / "specs" / "beta").mkdir(parents=True)
    (d / "specs" / "alpha").mkdir(parents=True)
    for name in ("tasks.md", "proposal.md", "design.md"):
        (d / name).write_text("# x\n", encoding="utf-8")
    for cap in ("alpha", "beta"):
        (d / "specs" / cap / "spec.md").write_text("# x\n", encoding="utf-8")
    # Never directory order: a reader should know where a tab is before looking.
    assert [k for k, _l, _p in OC.change_files(str(d))] == [
        "proposal", "design", "tasks", "spec-alpha", "spec-beta"]


def test_an_absent_design_file_is_simply_absent(tmp_path):
    d = tmp_path / "c"
    d.mkdir()
    for name in ("proposal.md", "tasks.md"):
        (d / name).write_text("# x\n", encoding="utf-8")
    assert [k for k, _l, _p in OC.change_files(str(d))] == ["proposal", "tasks"]
