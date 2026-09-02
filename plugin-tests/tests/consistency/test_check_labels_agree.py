"""Cross-file agreement on `checklist.md`'s high-yield check labels — PARTIAL, see scope.

`review-change/references/checklist.md` defines the numbered high-yield checks
(`0a`, `0b`, …), and other places in the plugin restate that set in prose. A
change that adds a check updates the definition and whichever restatements its
author happened to grep for; the rest go stale silently. That is how a check goes
quietly unrun, because an orchestrator reads the restatement to decide what to
run, not the definitions.

**What this guard actually covers, stated narrowly on purpose.** Five rules:

1. the checklist's own definitions form a contiguous run (a hole makes every
   range unsatisfiable);
2. no range in a watched file reaches past the highest defined label;
3. a line asserting which checks *live in* the checklist accounts for every
   label the checklist owns;
4. a `"the N high-yield checks"` count equals the number defined, and no other
   watched file defines a label the checklist already owns.

5. every line MARKED as enumerating the whole set (`<!-- enumerates-checks -->`)
   accounts for every defined label, with a floor on how many marked lines must
   exist.

**Rule 5 is the general form of rule 3, and it closed the gap this docstring
used to record.** Rule 3 fires only on the "live in checklist.md" idiom, which
exactly one line in the watched set uses, so the checklist's own internal
restatements — the parallel-batch-2 sentence, the orchestrator-runs-these line,
the INT-SYC clause — went stale with the suite green. A reviewer reproduced it.
Inferring "this sentence enumerates the set" from phrasing failed three times in
both directions, so the enumerating lines are now *marked* instead: an HTML
comment, invisible when rendered, greppable repo-wide, and legible to whoever
edits the prose next. Rule 3 is kept rather than replaced — it is a true
statement about a different thing (residence), and it subtracts delegated labels
where rule 5 does not.

**How the watched set is decided.** It is DISCOVERED, by scanning the plugin
tree for the marker, not handed over as a list. The list was four literal paths
and nothing detected a fifth enumerating file appearing — a file could carry a
marked enumeration and go unwatched forever, the same silence this guard exists
to remove one level down. Marking a line now enrols its file.

Two entry points are added on top of discovery because they advertise a check
count and name ranges without carrying a marker, and one file is exempted with
its reason: `agents/fact-gatherer.md` names a subset range in frontmatter as the
agent's own input, not as a run-these instruction. The exemption is itself
tested, so it cannot outlive the reason for it.

**Measured on `main` when this landed:** the guard caught three live defects that
predate it — `review-gate.md` told batch orchestrators that `0j` and `0k` do not
live in the checklist (so both were skipped), it defined its own colliding `0j`,
and both `SKILL.md` entry points advertised 10 checks for a set of 11.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_CHECKLIST = _PLUGIN_ROOT / "skills" / "review-change" / "references" / "checklist.md"

# A check definition opens a line, in either of the two forms the plugin uses:
# "0a. **Symbol reality check** — …" in the checklist, and
# "**0j — Cross-change cross-reference check…**" in review-gate.md.
# Matching only the first form is how a real collision stayed invisible: the
# checklist and review-gate.md each defined a different `0j`, and a guard that
# saw only one spelling reported no collision.
_DEFINITION = re.compile(r"^(?:\*\*)?(0[a-z])(?:\.|\s*[–—-])\s", re.MULTILINE)

# A range enumeration. Both the dash characters and the optional backticks are
# taken from how the prose is actually written: `0a`–`0e`, 0a–0e and 0a-0e all
# occur across these files, and a pattern that misses the backticked form reads
# a correct line as an incomplete one.
_RANGE = re.compile(r"`?\b(0[a-z])\b`?\s*[–—-]\s*`?\b(0[a-z])\b`?")

# "the 12 high-yield verification checks"
_COUNT = re.compile(r"\b(\d+)\s+high-yield(?:\s+verification)?\s+checks\b")

_ENUMERATION_MARKER = "<!-- enumerates-checks -->"

# Files that enumerate the checklist's checks. A file qualifies because it tells
# a reader which checks to run; a file that merely mentions one does not.
_REVIEW_GATE = _PLUGIN_ROOT / "skills" / "multi-spec" / "references" / "review-gate.md"

# DISCOVERED, not hand-listed. The list used to be four literal paths, and
# nothing detected a fifth enumerating file appearing — a file could carry a
# marked enumeration and go unwatched forever, which is the exact silence this
# guard exists to remove one level down. Discovery keys on the marker below, so
# marking a line is what enrols its file.
#
# Two files are added on top of discovery rather than found by it. Both are
# entry points that advertise a check COUNT and name ranges WITHOUT carrying a
# marker, so `test_range_enumerations_name_only_defined_checks` must still reach
# them; dropping them when discovery replaced the list would have narrowed this
# guard while appearing to widen it.
_STRUCTURAL_ENTRY_POINTS = (
    _PLUGIN_ROOT / "skills" / "review-change" / "SKILL.md",
    _PLUGIN_ROOT / "skills" / "spec-to-pr" / "SKILL.md",
)

# Deliberately UNMARKED, carried forward with its reason.
#
# `agents/fact-gatherer.md` names `0a`–`0h` in its frontmatter `description:` — a
# statement of what the agent is handed, not an instruction to an orchestrator
# about what to run. Marking it would enrol it in discovery and demand it name
# the whole defined set, which would be wrong: the agent really is given a
# subset.
#
# **This is a rule, not a filter.** The first draft also excluded these paths
# from the scan, and review measured that clause to be dead code: discovery keys
# on the marker, an unmarked file is never discovered, and the only state in
# which the filter removes anything is the exempt file carrying a marker — which
# `test_the_exemption_is_still_earned` asserts must never hold. A filter whose
# sole reachable effect is a red test is documentation wearing a mechanism's
# clothes. The rule is enforced by that test instead, so marking this file fails
# loudly and says why, rather than being silently honoured or silently ignored.
_UNMARKED_BY_DESIGN = {
    _PLUGIN_ROOT / "agents" / "fact-gatherer.md":
        "names a subset range in frontmatter as the agent's own input, not as a "
        "run-these instruction to an orchestrator",
}


def _discovered_enumerating_files(root: Path | None = None) -> list[Path]:
    """Every file under `root` carrying a marked enumeration.

    `root` is a parameter so the scanner can be fed a synthetic tree. Without
    one it could only ever be run against the live tree, where the defects it
    guards are absent by construction — and a test written against it then
    re-implements the scan inline and proves nothing about this function. That
    is what the first draft did: replacing this whole body with a hardcoded
    two-path list left all 24 tests green.
    """
    root = _PLUGIN_ROOT if root is None else root
    return sorted(
        path
        for path in root.rglob("*.md")
        if _ENUMERATION_MARKER in path.read_text(encoding="utf-8")
    )


def _enumerating_files() -> list[Path]:
    return sorted(set(_discovered_enumerating_files()) | set(_STRUCTURAL_ENTRY_POINTS))

# The checklist delegates a contiguous run of checks to the project overlay
# instead of defining them itself, on one line that opens with the range. The
# labels are READ from that line rather than hardcoded: an earlier draft pinned
# {0f,0g,0h,0i} behind the literal "0f–0i.", and applying to that heading the
# same backtick styling this guard's own commit applied elsewhere dropped four
# labels from the defined set and took the suite red with a message blaming the
# wrong prose. A guard that cries wolf on a cosmetic edit gets weakened.
_DELEGATION_LINE = re.compile(r"^`?(0[a-z])`?\s*[–—-]\s*`?(0[a-z])`?\.\s", re.MULTILINE)


def _expand(lo: str, hi: str) -> set[str]:
    if hi < lo:
        raise ValueError(
            f"inverted check range {lo}–{hi}: an inverted range expands to nothing, "
            "so it would contribute no coverage and trip no overrun — invisible in "
            "both directions. Fix the range rather than the guard."
        )
    return {f"0{chr(c)}" for c in range(ord(lo[1]), ord(hi[1]) + 1)}


def _defined_labels() -> set[str]:
    text = _CHECKLIST.read_text(encoding="utf-8")
    labels = set(_DEFINITION.findall(text))
    for lo, hi in _DELEGATION_LINE.findall(text):
        labels |= _expand(lo, hi)
    return labels


def _delegated_labels() -> set[str]:
    """Checks the checklist names but does not define — the overlay owns them."""
    text = _CHECKLIST.read_text(encoding="utf-8")
    delegated: set[str] = set()
    for lo, hi in _DELEGATION_LINE.findall(text):
        delegated |= _expand(lo, hi)
    return delegated


def test_checklist_defines_a_contiguous_run_of_checks() -> None:
    """The definitions themselves must not have a hole — a gap breaks every range."""
    defined = _defined_labels()
    assert defined, f"no check definitions found in {_CHECKLIST}"
    letters = sorted(label[1] for label in defined)
    expected = [chr(c) for c in range(ord("a"), ord(letters[-1]) + 1)]
    assert letters == expected, (
        f"{_CHECKLIST.name} defines {''.join(letters)} — expected a contiguous run "
        f"a..{letters[-1]}. A hole means some range enumeration is unsatisfiable."
    )


@pytest.mark.parametrize("path", _enumerating_files(), ids=lambda p: str(p.relative_to(_PLUGIN_ROOT)))
def test_range_enumerations_name_only_defined_checks(path: Path) -> None:
    """`0a–0k` in any enumerating file must not reach past what the checklist defines."""
    defined = _defined_labels()
    highest = max(defined)
    text = path.read_text(encoding="utf-8")

    overruns = []
    for lo, hi in _RANGE.findall(text):
        for label in _expand(lo, hi):
            if label not in defined:
                overruns.append(f"{lo}–{hi} reaches {label}")

    assert not overruns, (
        f"{path.relative_to(_PLUGIN_ROOT)} enumerates checks the checklist does not define: "
        f"{'; '.join(sorted(set(overruns)))}. The checklist defines up to {highest}."
    )


@pytest.mark.parametrize("path", _enumerating_files(), ids=lambda p: str(p.relative_to(_PLUGIN_ROOT)))
def test_each_enumerating_line_covers_the_whole_defined_set(path: Path) -> None:
    """A residence claim must account for every check the checklist defines.

    **Read the scope note in this module's docstring before relying on this.**
    It fires only on a line asserting which checks *live in* the checklist, and
    at the time of writing exactly one line in the watched set does so. It is
    NOT general coverage of every enumeration.

    That narrowness is the third attempt, and the two before it failed the other
    way. A presence check ("the newest label appears somewhere in the file")
    passes while another sentence in the same file enumerates the old set — the
    exact shape that shipped. Treating any range starting at `0a` as an
    enumeration false-positives on every legitimate subset that also starts
    there: `0a-0h` is the delegable portion, `0a-0e` appears in a comparison.

    A residence claim may split the set across several ranges, and need only
    account for what the checklist itself OWNS — the labels it delegates to the
    overlay are legitimately named as living elsewhere, so they are subtracted
    before comparing. Without that subtraction, reflowing one long line into two
    true bullets fails with a message that is factually wrong.
    """
    defined = _defined_labels()
    gaps = []
    claims_residence = re.compile(r"live[s]? in .?`?checklist\.md`?", re.IGNORECASE)

    owned = defined - _delegated_labels()
    matched_any = False

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not claims_residence.search(line):
            continue
        matched_any = True
        ranges = _RANGE.findall(line)
        assert ranges, (
            f"{path.name}:{lineno} claims which checks live in the checklist but "
            "names no range this guard can parse. That combination means the "
            "enumeration was rewritten into a shape the guard cannot read, which "
            "is indistinguishable from it being correct — so it fails rather than "
            f"skipping. Line: {line.strip()[:160]}"
        )
        covered: set[str] = set()
        for lo, hi in ranges:
            covered |= _expand(lo, hi)
        uncovered = owned - covered
        if uncovered:
            gaps.append(f"line {lineno} omits {', '.join(sorted(uncovered))}")

    assert not gaps, (
        f"{path.relative_to(_PLUGIN_ROOT)} enumerates the checks but does not account for all of them: "
        f"{'; '.join(gaps)}. A reader of that line runs the old set."
    )


def test_a_residence_claim_still_exists_somewhere_to_check() -> None:
    """The residence rule must have something to fire on, or it is silently inert.

    It matches one prose idiom, and at the time of writing exactly one line in
    the watched set uses it. A synonym reword of that line ("carries" for "live
    in") leaves the enumeration stale AND removes the guard's only live
    assertion, with every test still green. This turns that into a loud failure:
    zero residence claims across the whole corpus means the rule is checking
    nothing, whether or not the prose is correct.
    """
    claims_residence = re.compile(r"live[s]? in .?`?checklist\.md`?", re.IGNORECASE)
    hits = [
        f"{path.relative_to(_PLUGIN_ROOT)}:{n}"
        for path in _enumerating_files()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if claims_residence.search(line)
    ]
    assert hits, (
        "no line in the watched set claims which checks live in the checklist, so "
        "test_each_enumerating_line_covers_the_whole_defined_set is checking nothing. "
        "Either a residence claim was reworded past this rule's one idiom, or it was "
        "deleted. Restore the phrasing or widen the rule — do not leave it inert."
    )


# The general form of rule 3. A line that enumerates the whole check set carries
# an HTML comment saying so — invisible when the markdown renders, greppable
# repo-wide, and legible to whoever edits the prose next. Inferring the same
# thing from phrasing was tried three times and failed in both directions: a
# presence check passes while another sentence in the same file names the old
# set; treating any range opening at `0a` as an enumeration false-positives on
# every legitimate subset that also opens there (`0a–0h` is the delegable
# portion, `0a–0e` appears in a comparison). Marking is the only version that
# distinguishes "enumerates the set" from "mentions a range".

# The lines that MUST carry the marker, pinned by a stable substring rather than
# counted.
#
# A population floor was tried first and is not enough: it counts markers without
# pinning which lines hold them, so deleting the marker from the load-bearing line
# and adding one to a trivially-correct line elsewhere keeps the count and leaves
# the real enumeration unwatched. A reviewer built that swap and it survived. The
# floor stops markers being deleted; it does not stop them being MOVED, and the
# defect this rule exists for is a specific line going short.
#
# Pinned by substring, not by line number, so reflowing the prose does not break
# the pin. Each anchor must match exactly one line in its file — enforced below,
# because an anchor matching zero lines would silently pin nothing, and one
# matching several would pin the wrong one.
_REQUIRED_MARKED_LINES: tuple[tuple[Path, str, str], ...] = (
    (_CHECKLIST, "Parallel batch 2",
     "tells the orchestrator which checks to run in the parallel batch"),
    (_CHECKLIST, "All checks above",
     "the line an orchestrator reads to decide what it runs itself"),
    (_CHECKLIST, "INT-SYC (no sycophancy)",
     "names the checks that exist to refute an asserted premise"),
    (_REVIEW_GATE, "The verification work (checks",
     "the batch gate's own statement of what it batches"),
    (_REVIEW_GATE, "outside the `0[a-z]` namespace entirely",
     "explains why the batch-only check sits outside the checklist's namespace, "
     "by naming the set checklist.md owns"),
)


def _marked_lines(path: Path) -> list[tuple[int, str]]:
    return [
        (n, line)
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _ENUMERATION_MARKER in line
    ]


@pytest.mark.parametrize("path", _enumerating_files(), ids=lambda p: str(p.relative_to(_PLUGIN_ROOT)))
def test_every_marked_enumeration_covers_the_whole_defined_set(path: Path) -> None:
    """A marked line must name every check the checklist defines.

    This is the rule the residence idiom could only reach on one line. It covers
    the checklist's own internal restatements — the parallel-batch-2 sentence,
    the orchestrator-runs-these line, the INT-SYC clause — which are the lines an
    orchestrator actually reads to decide what to run, and which previously went
    stale with the suite green.

    Unlike the residence rule, delegated labels are NOT subtracted. A marked line
    claims the whole set: the one marked line that itemises the overlay's `0f–0i`
    accounts for them explicitly, and the rest cover them inside a full `0a–0l`
    range. A marked line that can do neither is mismarked.
    """
    defined = _defined_labels()
    gaps = []

    for lineno, line in _marked_lines(path):
        ranges = _RANGE.findall(line)
        assert ranges, (
            f"{path.name}:{lineno} is marked as enumerating the checks but names no "
            "range this guard can parse. A marked line that cannot be read is "
            "indistinguishable from a correct one, so it fails rather than skipping. "
            f"Line: {line.strip()[:160]}"
        )
        covered: set[str] = set()
        for lo, hi in ranges:
            covered |= _expand(lo, hi)
        uncovered = defined - covered
        if uncovered:
            gaps.append(f"line {lineno} omits {', '.join(sorted(uncovered))}")

    assert not gaps, (
        f"{path.relative_to(_PLUGIN_ROOT)} carries a marked enumeration that does not "
        f"account for every defined check: {'; '.join(gaps)}. An orchestrator reading "
        "that line runs the old set."
    )


@pytest.mark.parametrize(
    ("path", "anchor", "why"),
    _REQUIRED_MARKED_LINES,
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_each_load_bearing_enumeration_still_carries_its_marker(
    path: Path, anchor: str, why: str
) -> None:
    """Non-vacuity for the rule above, pinned per line rather than counted.

    Every assertion in `test_every_marked_enumeration_covers_the_whole_defined_set`
    sits inside a loop over marked lines, so with no markers it passes over an empty
    list and the rule evaporates with the suite green — the failure mode the
    residence idiom already had once.

    A population floor closed only half of that. It counts markers without pinning
    which lines carry them, so moving one — dropped from the load-bearing line,
    added to a trivially-correct line elsewhere — keeps the count while leaving the
    real enumeration unwatched. That swap was built and it survived. Pinning the
    line is what binds.
    """
    hits = [(n, line) for n, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1) if anchor in line]

    assert len(hits) == 1, (
        f"anchor {anchor!r} matches {len(hits)} lines in {path.name}, expected exactly 1. "
        "An anchor matching none pins nothing and this test passes vacuously; one "
        "matching several pins the wrong line. Re-anchor on text unique to the line "
        f"that {why}."
    )

    lineno, line = hits[0]
    assert _ENUMERATION_MARKER in line, (
        f"{path.relative_to(_PLUGIN_ROOT)}:{lineno} lost its `{_ENUMERATION_MARKER}` "
        f"marker. This line {why}, so an orchestrator reads it to decide what to run "
        "and it must be checked against the whole defined set. Restore the marker, or "
        "delete this entry from _REQUIRED_MARKED_LINES in the same commit and say why "
        f"the line no longer enumerates. Line: {line.strip()[:120]}"
    )


def test_advertised_check_count_matches_the_definitions() -> None:
    """"the N high-yield verification checks" must equal the number defined."""
    defined = _defined_labels()
    wrong = []
    for path in _enumerating_files():
        for claimed in _COUNT.findall(path.read_text(encoding="utf-8")):
            if int(claimed) != len(defined):
                wrong.append(f"{path.relative_to(_PLUGIN_ROOT)} says {claimed}")

    assert not wrong, (
        f"{_CHECKLIST.name} defines {len(defined)} checks ({''.join(sorted(defined))}), "
        f"but: {'; '.join(wrong)}."
    )


def test_no_file_redefines_a_label_the_checklist_owns() -> None:
    """A skill adding its own check must not reuse a checklist label.

    `review-gate.md` adds one batch-only check of its own. When it used `0j` —
    which the checklist also defines — an orchestrator that had already run
    checklist `0j` per change read "add check 0j" as work already done, and the
    one check that batch gate exists for was skipped, with the report identical
    either way.
    """
    defined = _defined_labels()
    collisions = []
    for path in _enumerating_files():
        if path == _CHECKLIST:
            continue
        for label in _DEFINITION.findall(path.read_text(encoding="utf-8")):
            if label in defined:
                collisions.append(f"{path.relative_to(_PLUGIN_ROOT)} defines {label}")

    assert not collisions, (
        f"these files define a check label {_CHECKLIST.name} already owns: "
        f"{'; '.join(collisions)}. Pick a label outside the checklist's range."
    )


def test_marking_a_file_is_what_enrols_it(tmp_path) -> None:
    """Discovery's mechanism, against a synthetic tree — calling production.

    The first draft of this test re-implemented the scan inline and never called
    `_discovered_enumerating_files`, so replacing that function's whole body with
    a hardcoded two-path list left every test green. It asserted that `in` works.
    This one calls the function, so a scanner that stops scanning is caught.
    """
    (tmp_path / "skills" / "newcomer").mkdir(parents=True)
    marked = tmp_path / "skills" / "newcomer" / "SKILL.md"
    marked.write_text(f"Run checks `0a`-`0l`. {_ENUMERATION_MARKER}\n", encoding="utf-8")
    (tmp_path / "skills" / "newcomer" / "quiet.md").write_text(
        "Mentions `0a` but claims no enumeration.\n", encoding="utf-8"
    )
    assert _discovered_enumerating_files(tmp_path) == [marked], (
        "marking a file must enrol it, and an unmarked file that merely mentions "
        "a label must not be enrolled."
    )


def test_discovery_reaches_outside_the_skills_directory(tmp_path) -> None:
    """The scan root covers the whole plugin, not just `skills/`.

    Both files that carry markers today live under `skills/`, so narrowing the
    scan root to `_PLUGIN_ROOT / "skills"` was measured to leave all 24 tests
    green while making `agents/`, `output-styles/`, `hooks/` and the plugin root
    unscannable. Only a synthetic tree can distinguish those two scan roots,
    because the live tree cannot.
    """
    for rel in ("agents/helper.md", "output-styles/CLA.md", "top-level.md"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"Checks `0a`-`0l`. {_ENUMERATION_MARKER}\n", encoding="utf-8")
    found = {p.relative_to(tmp_path).as_posix() for p in _discovered_enumerating_files(tmp_path)}
    assert found == {"agents/helper.md", "output-styles/CLA.md", "top-level.md"}, (
        f"discovery reached {sorted(found)}; a marked file outside `skills/` was "
        f"missed, so narrowing the scan root would go unnoticed."
    )


def test_the_discovery_finds_the_marked_files() -> None:
    """Discovery must not be silently empty, or every parametrized test vanishes.

    A `rglob` that matches nothing yields zero parametrize cases, and pytest
    reports zero cases as a pass. The floor tracks the real population — two
    files carry markers today, measured with
    `grep -rl 'enumerates-checks' .claude/plugins/cla/` -> 2. The identity pin
    below is strictly stronger; the floor is kept because it is what goes stale
    visibly when a third marked file lands, whereas the pin would silently keep
    passing while naming only two.
    """
    discovered = _discovered_enumerating_files()
    assert len(discovered) >= 2, (
        f"marker discovery found {len(discovered)} file(s), expected at least 2. "
        f"Either the marker {_ENUMERATION_MARKER!r} was reworded — update it here "
        f"in the same commit — or the marked enumerations were deleted."
    )
    assert _CHECKLIST in discovered and _REVIEW_GATE in discovered, (
        f"discovery missed a file known to carry markers: {sorted(discovered)}"
    )


def test_the_structural_entry_points_are_still_watched() -> None:
    """The union half, which discovery alone would have dropped.

    These two carry no marker but DO advertise a check count, so they are the
    entire population of `test_advertised_check_count_matches_the_definitions`.
    Emptying the tuple was measured to leave 18 tests passing while that rule
    went fully vacuous — the "narrowed the guard while appearing to widen it"
    failure, handled in the code and previously unguarded in the tests.
    """
    assert len(_STRUCTURAL_ENTRY_POINTS) >= 2, (
        f"{len(_STRUCTURAL_ENTRY_POINTS)} structural entry point(s); expected the "
        f"two that advertise a check count. Dropping one silently shrinks the "
        f"check-count rule's population toward zero."
    )
    for path in _STRUCTURAL_ENTRY_POINTS:
        assert path.exists(), f"structural entry point {path} no longer exists"
        assert _COUNT.search(path.read_text(encoding="utf-8")), (
            f"{path.name} is listed as a structural entry point because it "
            f"advertises a check count, but it no longer states one. Either the "
            f"phrasing changed — update `_COUNT` — or the entry is obsolete."
        )
    watched = _enumerating_files()
    for path in _STRUCTURAL_ENTRY_POINTS:
        assert path in watched, f"{path.name} is listed but not actually watched"


def test_the_unmarked_by_design_rule_is_still_earned() -> None:
    """A stale exemption is worse than none — it reads as a considered decision.

    Checks the property the reason actually names, not a generic one. The reason
    says the range sits in FRONTMATTER as the agent's own input, and that it is a
    SUBSET; an earlier draft asserted only that some range existed anywhere in
    the file, which passes when the range moves into the body as a run-these
    instruction — the exact case that should revoke the rule.
    """
    defined = _defined_labels()
    for path, reason in _UNMARKED_BY_DESIGN.items():
        assert path.exists(), f"{path} no longer exists: {reason}"
        body = path.read_text(encoding="utf-8")

        frontmatter = body.split("---")[1] if body.startswith("---") else ""
        ranges = _RANGE.findall(frontmatter)
        assert ranges, (
            f"{path.name} is unmarked by design because it {reason}, but its "
            f"frontmatter no longer names a check range. If the range moved into "
            f"the body it is being read as an instruction, and the rule is void."
        )
        for first, last in ranges:
            named = {lab for lab in defined if first <= lab <= last}
            assert named and named < defined, (
                f"{path.name} names `{first}`-`{last}`, which is not a proper "
                f"subset of the defined set {sorted(defined)}. The rule rests on "
                f"it being handed a subset; a full or overrunning range means it "
                f"should be marked and checked like any other enumeration."
            )

        assert _ENUMERATION_MARKER not in body, (
            f"{path.name} is unmarked by design but now carries "
            f"{_ENUMERATION_MARKER!r}. Marking it is a request to be watched, "
            f"which this rule refuses. Resolve one or the other — do not leave "
            f"the marker sitting there doing nothing."
        )
