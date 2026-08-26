"""Every enumeration of `checklist.md`'s high-yield checks must name the checks it defines.

`review-change/references/checklist.md` defines the numbered high-yield checks —
`0a`, `0b`, … — and several other places in the plugin *enumerate* that set in
prose: the sentence that launches parallel batch 2, the INT-SYC clause, both
`SKILL.md` entry points that advertise how many checks the checklist carries, and
`multi-spec/references/review-gate.md`, which tells a batch orchestrator which
checks live in the checklist and which live in an overlay.

Nothing compares them. A change that adds a check updates the definition and
whichever enumerations its author happened to grep for, and the rest go stale
silently — a stale enumeration is how a check goes quietly unrun, because the
orchestrator reads the enumeration to decide what to run, not the definitions.

Measured on the change that added `0l` (PR #158): its own commit asserted "all
three stale check enumerations updated", verified by a grep scoped to
`checklist.md` alone. Three more enumerations in three other files were untouched
— `review-gate.md` still said only `0a`–`0e` lived in the checklist, and both
`SKILL.md` entry points still advertised "10 high-yield verification checks" for
a set that had become twelve. The fix for that then collided the checklist's
numbering with `review-gate.md`'s own local `0j`, which this guard also catches.
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
_ENUMERATING_FILES = [
    _CHECKLIST,
    _PLUGIN_ROOT / "skills" / "review-change" / "SKILL.md",
    _PLUGIN_ROOT / "skills" / "spec-to-pr" / "SKILL.md",
    _PLUGIN_ROOT / "skills" / "multi-spec" / "references" / "review-gate.md",
]

# Labels the checklist delegates to the project overlay rather than defining
# itself. They are legitimately absent from the definition scan.
_OVERLAY_DELEGATED = {"0f", "0g", "0h", "0i"}


def _defined_labels() -> set[str]:
    text = _CHECKLIST.read_text(encoding="utf-8")
    labels = set(_DEFINITION.findall(text))
    # "0f–0i." opens one line delegating four checks to the overlay.
    if "0f–0i." in text or "0f-0i." in text:
        labels |= _OVERLAY_DELEGATED
    return labels


def _expand(lo: str, hi: str) -> set[str]:
    return {f"0{chr(c)}" for c in range(ord(lo[1]), ord(hi[1]) + 1)}


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


@pytest.mark.parametrize("path", _ENUMERATING_FILES, ids=lambda p: p.name)
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
        f"{path.name} enumerates checks the checklist does not define: "
        f"{'; '.join(sorted(set(overruns)))}. The checklist defines up to {highest}."
    )


@pytest.mark.parametrize("path", _ENUMERATING_FILES, ids=lambda p: p.name)
def test_each_enumerating_line_covers_the_whole_defined_set(path: Path) -> None:
    """A line enumerating the checks from `0a` must account for all of them.

    This is the half that actually went stale, and the presence check that
    preceded it was too weak to see it: asserting the newest label appears
    *somewhere in the file* passes happily while a sentence elsewhere in that
    same file still enumerates the old, shorter set — which is exactly the shape
    `review-gate.md` shipped in.

    A line is treated as enumerating the set only when it asserts which checks
    *live in* the checklist. That phrasing is the narrow, reliable signal, and
    the narrowness is deliberate: an earlier draft of this guard treated any
    range starting at `0a` as an enumeration, which false-positives on every
    legitimate subset that also starts there — `0a–0h` is the delegable portion,
    and `0a–0e` appears in a comparison. Broad-and-wrong is worse than
    narrow-and-true, because a guard that cries wolf gets weakened or deleted.

    Such a line may split the set across several ranges — "0a–0e and 0j–0l live
    here; 0f–0i live in the overlay" is correct and common — so the UNION of its
    ranges is what must cover the defined labels, not any one range.
    """
    defined = _defined_labels()
    gaps = []
    claims_residence = re.compile(r"live[s]? in .?`?checklist\.md`?", re.IGNORECASE)

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not claims_residence.search(line):
            continue
        ranges = _RANGE.findall(line)
        if not ranges:
            continue
        covered: set[str] = set()
        for lo, hi in ranges:
            covered |= _expand(lo, hi)
        uncovered = defined - covered
        if uncovered:
            gaps.append(f"line {lineno} omits {', '.join(sorted(uncovered))}")

    assert not gaps, (
        f"{path.name} enumerates the checks but does not account for all of them: "
        f"{'; '.join(gaps)}. A reader of that line runs the old set."
    )


def test_advertised_check_count_matches_the_definitions() -> None:
    """"the N high-yield verification checks" must equal the number defined."""
    defined = _defined_labels()
    wrong = []
    for path in _ENUMERATING_FILES:
        for claimed in _COUNT.findall(path.read_text(encoding="utf-8")):
            if int(claimed) != len(defined):
                wrong.append(f"{path.name} says {claimed}")

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
                collisions.append(f"{path.name} defines {label}")

    assert not collisions, (
        f"these files define a check label {_CHECKLIST.name} already owns: "
        f"{'; '.join(collisions)}. Pick a label outside the checklist's range."
    )
