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
    # `cla-init` is eight characters and named a skill mentioned repo-wide;
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
    this repo's own change listed `sync-context` among its candidates and was
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


SPEC_ONLY = """# Delta: cla-plugin

## MODIFIED Requirements

### Requirement: Project-data scaffolding

Text.
"""


def _impact_only(impact_line):
    """A proposal with no `## Capabilities` section: the capability, if it is
    named at all, is named under `## Impact` — the shape most proposals use."""
    return ("# P\n\n## Why\n\nBecause.\n\n## What Changes\n\n- Rework the thing\n\n"
            "## Impact\n\n- %s\n" % impact_line)


def _cap_row(prop, name="cla-plugin"):
    m = OC.build("demo", {"proposal": prop, "spec-cla-plugin": SPEC_ONLY})
    return m, [r for r in m["coverage"]["capabilities"] if r["name"] == name]


def test_a_capability_backticked_under_impact_counts_as_named():
    _m, rows = _cap_row(_impact_only("`cla-plugin`: one requirement modified"))
    assert len(rows) == 1
    assert rows[0]["mentioned"] and not rows[0]["named"] and rows[0]["delta"]
    assert rows[0]["why"] == ""


def test_a_bare_mention_in_another_case_counts_as_named():
    _m, rows = _cap_row(_impact_only("The CLA-Plugin spec loses one scenario"))
    assert rows[0]["mentioned"]
    assert rows[0]["why"] == ""


def test_a_longer_name_containing_the_capability_is_not_a_mention():
    # Both sides: a suffix and a prefix. Either one alone leaves the other
    # boundary free to break without a test noticing.
    for line in ("`cla-plugin-extra` gains a requirement",
                 "`old-cla-plugin` gains a requirement"):
        _m, rows = _cap_row(_impact_only(line))
        assert not rows[0]["mentioned"], line
        assert "no proposal capability names" in rows[0]["why"], line


def test_a_segment_of_a_nested_capability_path_is_not_a_mention():
    """A capability is a path: `identity/user-auth` names one capability, and
    the `user-auth` inside it is not a second one."""
    prop = _impact_only("`identity/user-auth`: login gains a requirement")
    m = OC.build("demo", {"proposal": prop, "spec-user-auth": SPEC_ONLY,
                          "spec-identity/user-auth": SPEC_ONLY})
    rows = {r["name"]: r for r in m["coverage"]["capabilities"]}
    assert rows["identity/user-auth"]["mentioned"] and rows["identity/user-auth"]["why"] == ""
    assert not rows["user-auth"]["mentioned"]
    assert "no proposal capability names" in rows["user-auth"]["why"]
    # And the other way round: the path's last segment is not the path's parent.
    m = OC.build("demo", {"proposal": _impact_only("`identity/user-auth` changes"),
                          "spec-identity": SPEC_ONLY})
    assert not m["coverage"]["capabilities"][0]["mentioned"]


def test_a_mention_adds_no_link():
    # A mention clears the coverage flag and nothing more: it is not a citation,
    # so it must not produce the strong link a `## Capabilities` bullet does.
    m, _rows = _cap_row(_impact_only("`cla-plugin`: one requirement modified"))
    assert not [l for l in m["links"]
                if any(i.startswith("spec-cla-plugin:") for i in (l["src"], l["dst"]))]


def test_a_mention_with_no_delta_adds_no_row():
    m = OC.build("demo", {"proposal": _impact_only("`other-cap` is untouched")})
    assert m["coverage"]["capabilities"] == []


# ---------------------------------------------------------------- requirement diffs


DIFF_DELTA = """# Delta: cla-plugin

## ADDED Requirements

### Requirement: Something new

The page SHALL do a new thing.

## MODIFIED Requirements

### Requirement: Project-data scaffolding

The setup SHALL write one facts file and SHALL ask before overwriting it.

#### Scenario: A fresh repo

- **WHEN** setup runs
- **THEN** one file is written

## REMOVED Requirements

### Requirement: Sync provenance lockfile

**Reason**: Gone.
"""

MAIN_SPEC = """# cla-plugin Specification

## Requirements

### Requirement: Project-data scaffolding

The setup SHALL write two facts files and SHALL ask before overwriting it.

#### Scenario: A fresh repo

- **WHEN** setup runs
- **THEN** one file is written

### Requirement: Sync provenance lockfile

Old.
"""


def _diffs(main_specs, archived=False, delta=DIFF_DELTA):
    m = OC.build("demo", {"proposal": PROPOSAL, "spec-cla-plugin": delta},
                 main_specs, archived)
    return list(m["diffs"].values())


def test_only_a_modified_requirement_gets_a_diff():
    recs = _diffs({"cla-plugin": MAIN_SPEC})
    assert len(recs) == 1 and recs[0]["cap"] == "cla-plugin"


def test_a_changed_word_shows_as_a_deletion_and_an_insertion():
    rec = _diffs({"cla-plugin": MAIN_SPEC})[0]
    assert rec["state"] == "diff"
    assert ("del", ["two"]) in rec["ops"] and ("ins", ["one"]) in rec["ops"]
    assert ("del", ["files"]) in rec["ops"] and ("ins", ["file"]) in rec["ops"]
    # The deletion is the MAIN spec's word: base and new are not interchangeable.
    assert ("del", ["one"]) not in rec["ops"]


def test_an_unchanged_requirement_is_reported_same():
    same = MAIN_SPEC.replace("two facts files", "one facts file")
    rec = _diffs({"cla-plugin": same})[0]
    assert rec["state"] == "same" and rec["ops"] == []


def test_a_long_unchanged_run_collapses_to_context_either_side():
    words = " ".join("w%d" % i for i in range(40))
    base = "## Requirements\n\n### Requirement: Project-data scaffolding\n\nA %s Z\n" % words
    new = "## MODIFIED Requirements\n\n### Requirement: Project-data scaffolding\n\nB %s Y\n" % words
    rec = _diffs({"cla-plugin": base}, delta=new)[0]
    tags = [t for t, _w in rec["ops"]]
    assert tags == ["del", "ins", "eq", "gap", "eq", "del", "ins"]
    assert rec["ops"][2][1] == ["w0", "w1", "w2", "w3", "w4", "w5"]
    assert rec["ops"][3][1] == 28
    assert rec["ops"][4][1] == ["w34", "w35", "w36", "w37", "w38", "w39"]


def test_no_main_spec_and_no_matching_requirement_are_their_own_states():
    assert _diffs({})[0]["state"] == "no-main-spec"
    assert _diffs({"cla-plugin": None})[0]["state"] == "no-main-spec"
    other = MAIN_SPEC.replace("Project-data scaffolding", "Something else")
    assert _diffs({"cla-plugin": other})[0]["state"] == "not-in-main"


def test_an_unreadable_main_spec_is_reported_not_raised():
    rec = _diffs({"cla-plugin": ValueError("not valid UTF-8")})[0]
    assert rec["state"] == "unreadable" and "UTF-8" in rec["why"]


def test_an_archived_change_is_never_compared():
    """Archiving wrote the new text into the main spec, so a comparison would
    report every requirement unchanged — which is false. `archived` is checked
    before anything else."""
    same = MAIN_SPEC.replace("two facts files", "one facts file")
    for main in ({"cla-plugin": same}, {"cla-plugin": MAIN_SPEC}, {},
                 {"cla-plugin": ValueError("x")}):
        assert _diffs(main, archived=True)[0]["state"] == "archived"


def test_a_modified_header_matches_the_main_spec_ignoring_whitespace_only():
    """OpenSpec matches a MODIFIED header to the main spec whitespace-
    insensitively and otherwise exactly, so a header in another case is a
    different requirement."""
    spaced = MAIN_SPEC.replace("### Requirement: Project-data scaffolding",
                               "### Requirement:   Project-data   scaffolding ")
    assert _diffs({"cla-plugin": spaced})[0]["state"] == "diff"
    cased = MAIN_SPEC.replace("Project-data scaffolding", "Project-Data Scaffolding")
    assert _diffs({"cla-plugin": cased})[0]["state"] == "not-in-main"


def test_the_diff_covers_every_scenario_of_the_requirement():
    """A MODIFIED block carries the full updated requirement, scenarios
    included, so a changed scenario is a changed requirement."""
    same = MAIN_SPEC.replace("two facts files", "one facts file")
    rec = _diffs({"cla-plugin": same.replace("one file is written",
                                             "a file is written")})[0]
    assert rec["state"] == "diff"
    assert ("del", ["a"]) in rec["ops"] and ("ins", ["one"]) in rec["ops"]


def test_no_main_specs_means_no_diffs():
    assert OC.build("demo", TEXTS)["diffs"] == {}


# ---------------------------------------------------------------- overview


# The OpenSpec 1.14 templates' shapes: a proposal with New and Modified
# Capabilities, a new capability's delta opening with `## Purpose`, a RENAMED
# group of FROM/TO bullets.
OV_PROPOSAL = """# Proposal

## Why

Reviewers compare requirements by eye. That is slow.

A second paragraph that is not the why's first.

## What Changes

- **BREAKING** — rename `src/auth/login.py` and drop the old entry point
- A calmer palette for the login page

## Capabilities

### New Capabilities

- `identity/user-auth`: signing in

### Modified Capabilities

- `billing`: invoices name the signed-in user

## Impact

- `audit-log` gains nothing
"""

OV_NEW_DELTA = """# Spec Delta

## Purpose

Signing in to the product, and what a session may do once it exists.

## ADDED Requirements

### Requirement: Signing in

The product SHALL let a user sign in.

#### Scenario: A known user
- **WHEN** a known user signs in
- **THEN** a session starts
"""

OV_MODIFIED_DELTA = """# Spec Delta

## MODIFIED Requirements

### Requirement: Invoices

Invoices SHALL name the user.

#### Scenario: An invoice
- **WHEN** an invoice is made
- **THEN** it names the user

## REMOVED Requirements

### Requirement: Paper invoices

**Reason**: Nobody prints them.
**Migration**: None.

## RENAMED Requirements

- FROM: `### Requirement: Bills`
- TO: `### Requirement: Invoices`
"""

OV_TASKS = """# Tasks

## 1. Auth

- [x] 1.1 Rename `src/auth/login.py`
- [ ] 1.2 Write the palette
"""

OV_TEXTS = {"proposal": OV_PROPOSAL, "tasks": OV_TASKS,
            "spec-identity/user-auth": OV_NEW_DELTA, "spec-billing": OV_MODIFIED_DELTA}


def _ov(main_specs=None, texts=OV_TEXTS, **kw):
    return OC.overview(OC.build("demo", texts, main_specs, **kw), texts)


def test_the_overview_why_is_the_first_paragraph_of_why():
    assert _ov()["why"] == "Reviewers compare requirements by eye. That is slow."


def test_each_promise_carries_the_bucket_coverage_put_it_in():
    got = [(c["num"], b) for c, b in _ov()["promises"]]
    assert got == [("p1", "covered"), ("p2", "unchecked")]


def test_a_breaking_promise_is_marked():
    ov = _ov()
    ids = {c["num"]: c["id"] for c, _b in ov["promises"]}
    assert ov["breaking"] == {ids["p1"]}


def test_the_overview_counts_requirements_by_group_and_renames_by_pair():
    ov = _ov()
    assert ov["reqs"] == {"billing": {"ADDED": 0, "MODIFIED": 1, "REMOVED": 1},
                          "identity/user-auth": {"ADDED": 1, "MODIFIED": 0, "REMOVED": 0}}
    assert ov["renamed"] == {"billing": 1, "identity/user-auth": 0}
    assert ov["tasks"] == (1, 2)


def test_a_capability_is_new_when_listed_new_or_opening_with_purpose_or_without_a_main_spec():
    main = {"billing": "# billing\n\n## Requirements\n", "identity/user-auth": "# x\n"}
    assert _ov(main)["new"] == {"billing": False, "identity/user-auth": True}
    # Not listed under New Capabilities, but its delta opens with `## Purpose`.
    prop = OV_PROPOSAL.replace("### New Capabilities\n\n- `identity/user-auth`: signing in\n", "")
    texts = dict(OV_TEXTS, proposal=prop)
    assert _ov(main, texts)["new"]["identity/user-auth"] is True
    # Neither listed nor opening with Purpose: new only because no main spec exists.
    texts["spec-identity/user-auth"] = OV_NEW_DELTA.replace(
        "## Purpose\n\nSigning in to the product, and what a session may do once it exists.\n\n", "")
    assert _ov(main, texts)["new"]["identity/user-auth"] is False
    assert _ov(dict(main, **{"identity/user-auth": None}), texts)["new"]["identity/user-auth"] is True
    # A capability whose main spec was never looked up is not called new for it.
    assert _ov({}, texts)["new"]["identity/user-auth"] is False
    # Listed under New Capabilities, no Purpose, a main spec present: the listing
    # alone makes it new.
    texts["proposal"] = OV_PROPOSAL
    assert _ov(main, texts)["new"]["identity/user-auth"] is True


def test_purpose_is_not_a_requirement_group():
    delta = ("# Spec Delta\n\n## REMOVED Requirements\n\n### Requirement: Old\n\n"
             "**Reason**: Gone.\n\n## Purpose\n\n### Requirement: Stray\n\nText.\n")
    groups = {c["text"]: c["group"] for c in OC.requirements(delta, "spec-x")}
    assert groups == {"Old": "REMOVED", "Stray": ""}


def test_skip_specs_quiets_the_missing_delta_and_says_so():
    texts = {"proposal": OV_PROPOSAL, "tasks": OV_TASKS}
    m = OC.build("demo", texts, skip_specs=True)
    assert [r["why"] for r in m["coverage"]["capabilities"]] == ["", ""]
    assert OC.overview(m, texts)["skip_specs"] is True
    flagged = OC.build("demo", texts)["coverage"]["capabilities"]
    assert all("no specs/" in r["why"] for r in flagged)


def test_skip_specs_is_read_from_the_top_level_key_only():
    assert OC.skip_specs_set("schema: spec-driven\nskip_specs: true\n")
    assert OC.skip_specs_set("skip_specs: True  # no deltas\n")
    assert not OC.skip_specs_set("schema: spec-driven\nskip_specs: false\n")
    assert not OC.skip_specs_set("# skip_specs: true\n")
    assert not OC.skip_specs_set("other:\n  skip_specs: true\n")


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


def test_a_nested_capability_path_gets_its_own_file(tmp_path):
    """OpenSpec 1.14 capability paths may have several segments, and the delta
    lives at specs/<path>/spec.md. Listing one level only gave it no tab."""
    d = tmp_path / "c"
    (d / "specs" / "identity" / "user-auth").mkdir(parents=True)
    (d / "specs" / "billing").mkdir(parents=True)
    (d / "proposal.md").write_text("# Proposal\n", encoding="utf-8")
    for cap in ("identity/user-auth", "billing"):
        (d / "specs" / cap / "spec.md").write_text("# Spec Delta\n", encoding="utf-8")
    got = [(k, label) for k, label, _p in OC.change_files(str(d))]
    assert got == [("proposal", "proposal"), ("spec-billing", "spec · billing"),
                   ("spec-identity/user-auth", "spec · identity/user-auth")]


TASKS_114 = """# Tasks

## 1. Markers

- [ ] 1.1 Not started
- [x] 1.2 Done, lower case
- [X] 1.3 Done, upper case
- [ x] 1.4 Done, with a space before the mark
- [~] 1.5 In progress
- [-] 1.6 Dropped
- [] 1.7 An empty box
- [docs](notes.md) is a link, not a task
- [1](notes.md) is a one-character link, not a task
- [README] is a word in brackets, not a task

## Workflow follow-up

- Archive the change once it merges
- [ ] Not tracked either, though it carries a box
"""


def test_a_box_holding_only_x_is_done_and_every_other_mark_is_unfinished():
    """OpenSpec 1.14 counts a box holding only `x`, either case and any
    spacing, as done; `[~]`, `[-]` and `[]` are unfinished tasks. The old
    pattern dropped all four out of the total, and missed `[ x]` as done."""
    got = {c["num"]: c["done"] for c in OC.tasks(TASKS_114)}
    assert got == {"1.1": False, "1.2": True, "1.3": True, "1.4": True,
                   "1.5": False, "1.6": False, "1.7": False}


def test_workflow_follow_up_bullets_are_never_tasks():
    assert not [c for c in OC.tasks(TASKS_114) if c["group"] == "Workflow follow-up"]
    st = OC.build("demo", {"proposal": PROPOSAL, "tasks": TASKS_114})["coverage"]["stats"]
    assert (st["tasks_done"], st["tasks"]) == (3, 7)


def test_an_absent_design_file_is_simply_absent(tmp_path):
    d = tmp_path / "c"
    d.mkdir()
    for name in ("proposal.md", "tasks.md"):
        (d / name).write_text("# x\n", encoding="utf-8")
    assert [k for k, _l, _p in OC.change_files(str(d))] == ["proposal", "tasks"]
