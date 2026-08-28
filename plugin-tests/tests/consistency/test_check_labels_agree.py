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

**What it still does NOT cover.** `_ENUMERATING_FILES` is a hand-maintained list.
`agents/fact-gatherer.md` names a range in its frontmatter and is deliberately
unwatched; nothing detects a fifth file appearing. The marker makes that
findable by grep, but no rule here reads outside the four listed files.

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

# Files that enumerate the checklist's checks. A file is listed here because it
# tells a reader which checks to run; a file that merely mentions one is not.
_REVIEW_GATE = _PLUGIN_ROOT / "skills" / "multi-spec" / "references" / "review-gate.md"

_ENUMERATING_FILES = [
    _CHECKLIST,
    _PLUGIN_ROOT / "skills" / "review-change" / "SKILL.md",
    _PLUGIN_ROOT / "skills" / "spec-to-pr" / "SKILL.md",
    _REVIEW_GATE,
]

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


@pytest.mark.parametrize("path", _ENUMERATING_FILES, ids=lambda p: str(p.relative_to(_PLUGIN_ROOT)))
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


@pytest.mark.parametrize("path", _ENUMERATING_FILES, ids=lambda p: str(p.relative_to(_PLUGIN_ROOT)))
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
        for path in _ENUMERATING_FILES
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
_ENUMERATION_MARKER = "<!-- enumerates-checks -->"

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
    (_REVIEW_GATE, "not `0j`:",
     "explains the 0m label by naming the set checklist.md owns"),
)


def _marked_lines(path: Path) -> list[tuple[int, str]]:
    return [
        (n, line)
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _ENUMERATION_MARKER in line
    ]


@pytest.mark.parametrize("path", _ENUMERATING_FILES, ids=lambda p: str(p.relative_to(_PLUGIN_ROOT)))
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
    for path in _ENUMERATING_FILES:
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
    for path in _ENUMERATING_FILES:
        if path == _CHECKLIST:
            continue
        for label in _DEFINITION.findall(path.read_text(encoding="utf-8")):
            if label in defined:
                collisions.append(f"{path.relative_to(_PLUGIN_ROOT)} defines {label}")

    assert not collisions, (
        f"these files define a check label {_CHECKLIST.name} already owns: "
        f"{'; '.join(collisions)}. Pick a label outside the checklist's range."
    )
