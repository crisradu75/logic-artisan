"""Conformance guard: synced core must not hardcode its own install location.

A plugin installed from a marketplace does NOT live at
`<repo>/.claude/plugins/cla/`. It lives in a version-keyed cache directory that
changes on every update. So every skill instruction that says

    python3 .claude/plugins/cla/skills/_shared/scripts/git_state.py

is a command that works only in the one repo that develops the plugin with
`--plugin-dir`, and fails with "No such file or directory" in every repo that
installs it. This was measured, not imagined: 92 such paths across 31 files were
found immediately before the first consuming-repo test.

The fix is `${CLAUDE_PLUGIN_ROOT}`, which Claude Code substitutes in **skill and
agent content — anywhere the placeholder appears** (verified against
code.claude.com/docs/en/plugins-reference, not assumed).

WHY THIS IS A GUARD AND NOT A CONVENTION. The failure is invisible in the source
repo: here the hardcoded path resolves, because here the plugin really is at that
location. Nothing in a green suite, a review, or a manual run in this repo can
show it. Only a consuming repo sees it, and only at the moment a skill tries to
run a script.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

BAD = ".claude/plugins/cla"
# `hooks/` is scanned too, and so are `.py`/`.mjs`/`.json`. The first version
# covered only `*.md` under three roots, which left the guard blind to exactly
# the surfaces that still held the literal path: a usage comment in
# `mechanical-checks.mjs`, one in `_dispatch_lib.py`, and anything in
# `hooks/hooks.json`. A guard that cannot see where the defect actually lives is
# a guard that reports clean.
SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")
SCANNED_SUFFIXES = (".md", ".py", ".mjs", ".json")

# What the scanner is REQUIRED to reach, written down independently of the
# constant above rather than derived from it. The duplication is the point.
#
# `test_the_scan_is_not_vacuous` first compared `SCANNED_SUFFIXES` against the
# suffixes actually reached — and that comparison is a tautology, because
# `_scanned_files` filters on `SCANNED_SUFFIXES` itself. Delete a suffix and it
# leaves the declaration and the file set in the same edit, so the difference
# stays empty and the assertion passes. It could not react to the one edit it
# was added to catch. Three reviewers found it independently; one patched the
# constant in a throwaway interpreter and measured the assertion still green.
#
# An expectation read from the thing under test measures nothing. This second
# list is the independent source, so removing a suffix from `SCANNED_SUFFIXES`
# now fails loudly here instead of shrinking the scan in silence.
#
# THAT THIS ASSERTION FIRES IS ESTABLISHED BY A COMMAND, NOT BY THE BATCH.
# `plugin-tests/mutants/conformance/test_shipped_files_are_scanned.py` re-breaks
# the `.mjs` case, but TWO guards fail on it (that batch entry says which), so a
# kill there does not attribute itself here — the batch reports killed/survived
# over a whole directory and cannot separate them. No single-edit mutant can:
# isolating this needs a suffix with exactly one file that another scanner also
# reaches, and no such suffix exists. So it is measured directly instead::
#
#     $ python - <<'PY'
#     import importlib.util, pathlib
#     p = pathlib.Path("plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py")
#     def load():
#         s = importlib.util.spec_from_file_location("m", p.resolve())
#         m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
#     for drop in (".json", ".mjs", ".py", ".md", None):
#         m = load()
#         if drop:
#             m.SCANNED_SUFFIXES = tuple(x for x in m.SCANNED_SUFFIXES if x != drop)
#         files = list(m._scanned_files())
#         print(drop, len(files), sorted(m.REQUIRED_SUFFIXES - {f.suffix for f in files}))
#     PY
#     .json 100 ['.json']  .mjs 102 ['.mjs']  .py 73 ['.py']   .md 34 ['.md']  None 103 []
#
# The `.mjs` row is the load-bearing one: 102 clears the floor, so only this
# assertion is left. Against the tautological version that column was `[]` in
# every row — which is what "it could not react" means, measured.
REQUIRED_SUFFIXES = frozenset({".md", ".py", ".mjs", ".json"})

# The same independent-list argument, for the OTHER axis of the scan. Five roots
# are declared above and only `agents/` was ever asserted, so dropping
# `output-styles` or `lib` left the run green — measured, and recorded as a
# standing weakness in this guard's mutant batch:
#
#     drop `output-styles`  102 files, floor >= 98, every required suffix reached
#     drop `lib`            101 files, floor >= 98, every required suffix reached
#
# Neither root holds the last file of any required suffix and neither is large
# enough for the count to notice, so both the floor and the suffix comparison
# pass while a fifth of the declared root list has stopped being opened.
#
# WHY THIS IS A SEPARATE LIST AND NOT A PER-ROOT NON-EMPTINESS CHECK. "every
# entry of SCANNED_ROOTS contributes at least one file" is derived from
# `SCANNED_ROOTS` itself, so deleting an entry removes it from BOTH sides of the
# comparison in one edit and the assertion stays green — the exact tautology
# `REQUIRED_SUFFIXES` above was added to replace, three reviewers deep. This list
# is the independent source: removing a root from the scan now fails here.
REQUIRED_ROOTS = frozenset({"skills", "agents", "output-styles", "hooks", "lib"})

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"


def _scanned_files_by_root():
    """`(root_name, path)` per scanned file — the root identity `_scanned_files`
    throws away at the yield.

    Kept as the primitive rather than as a change to `_scanned_files`'s return
    shape: `test_shipped_files_are_scanned.py` calls that function directly and
    its own docstring says so, so widening it here would be the cross-directory
    caller break CLAUDE.md's fifth check is about."""
    for root_name in SCANNED_ROOTS:
        root = _PLUGIN_ROOT / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in SCANNED_SUFFIXES:
                continue
            parts = path.relative_to(_PLUGIN_ROOT).parts
            if "__pycache__" in parts or ".pytest_cache" in parts:
                continue
            yield root_name, path


def _scanned_files():
    for _root, path in _scanned_files_by_root():
        yield path


def _offenders():
    hits = []
    for path in _scanned_files():
        rel = path.relative_to(_PLUGIN_ROOT).as_posix()
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            if BAD in line:
                hits.append((rel, lineno, line.strip()[:120]))
    return hits


def test_synced_core_does_not_hardcode_the_plugin_install_path():
    offenders = _offenders()
    if offenders:
        detail = "\n".join(f"  {rel}:{n}  {text}" for rel, n, text in offenders)
        pytest.fail(
            f"{len(offenders)} hardcoded plugin path(s) in synced core. These "
            f"resolve in this repo and fail in every repo that installs the "
            f"plugin from a marketplace. Use ${{CLAUDE_PLUGIN_ROOT}} instead:\n"
            + detail
        )


def test_the_scan_is_not_vacuous():
    """A guard that scans nothing passes forever, and two guards in this repo
    already did once."""
    files = list(_scanned_files())
    # Re-measured with this file's own `__main__`, which is why it has one::
    #
    #     $ python plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py
    #     scanned 102  .json 3  .md 69  .mjs 1  .py 29  placeholder-refs 233 in 53 files
    #
    # The real count is 102. Pinned near it, not
    # comfortably below it, matching the rule `test_subprocess_encoding.py`
    # states for its own floor: move it to the new real count when something is
    # deliberately added or deleted, never to a number chosen to be safe from
    # future deletions. That leaves a margin of exactly one, which is the
    # philosophy working as intended rather than a defect to pad out: the next
    # deliberate deletion is EXPECTED to trip this floor and get it lowered
    # along with it, so a false sense of headroom is exactly what "pinned near
    # it" is for this guard to not have.
    #
    # IT HAS DRIFTED TWICE, and only the first was ever written down.
    #
    #   * floor 95 against a comment claiming 96, while the real count had risen
    #     to 99 — four files of headroom, which is precisely the decorative floor
    #     the rule above forbids.
    #   * floor 98 against a comment claiming 99, while the real count had risen
    #     to 103 — FIVE files of headroom, the drift issue #246 reported. It was
    #     corrected without leaving a trace, so this file's own record made the
    #     problem look like it had happened once.
    #
    # Both were found by someone running the printer for an unrelated reason.
    # The printer has been here the whole time: a printer nobody runs is not a
    # defence, and `test_the_recorded_counts_are_the_real_ones` is the one that
    # runs it. The floor above stays hand-pinned deliberately — a floor that
    # re-derives itself moves to meet any collapse and asserts nothing — so what
    # is checked automatically is the RECORD, not the bound.
    assert len(files) >= 101, f"scan set collapsed to {len(files)} files"
    assert any(
        p.relative_to(_PLUGIN_ROOT).as_posix().startswith("agents/") for p in files
    ), "agents/ is not being scanned"
    # Every REQUIRED suffix is actually reached. Two directions, one assertion,
    # and `REQUIRED_SUFFIXES` above explains why the expectation is a separate
    # list rather than `SCANNED_SUFFIXES` itself.
    #
    # Direction one: a suffix removed from `SCANNED_SUFFIXES`. This is why the
    # floor cannot be the whole defence — a suffix contributing fewer files than
    # the floor's margin drops out without moving the count below it. `.mjs` is
    # one file against a margin of one, so dropping it lands exactly ON the
    # floor and passes it. `hooks/hooks.json` is the sharper case: it was
    # covered here and nowhere else until issue #190 widened the token scanner
    # to `.json`, and once a second scanner reached it, the coverage guard in
    # `test_shipped_files_are_scanned.py` stopped noticing THIS scanner losing
    # it. Today the floor happens to catch a `.json` drop (103 - 3 = 100 < 102),
    # but that is arithmetic, not a guarantee: the comment above prescribes
    # lowering the floor on a deliberate deletion, and a floor lowered to 96
    # hands the `.json` narrowing a green run. And this is not hypothetical:
    # the parenthetical was left unre-run through a widening and INVERTED —
    # it read `99 - 3 = 96 < 98` while the real drop left 100 against a floor
    # of 98, i.e. the arithmetic it cited had stopped holding and the suffix
    # assertion was carrying the case alone. This assertion does not move.
    #
    # Direction two: the last file of a declared suffix leaving the TREE, which
    # is a real loss the floor's margin can also absorb.
    reached = {p.suffix for p in files}
    missing = sorted(REQUIRED_SUFFIXES - reached)
    assert not missing, (
        f"suffix(es) this scanner must reach but does not: {missing}. Either a "
        f"suffix was dropped from SCANNED_SUFFIXES, or the last file carrying it "
        f"left the tree. Both shrink the scan silently."
    )
    # The other direction, and it is silent without this line. The assertion
    # above is `REQUIRED - reached`, so ADDING a suffix to `SCANNED_SUFFIXES`
    # without adding it to `REQUIRED_SUFFIXES` passes: the new suffix is reached,
    # nothing is missing, and it carries exactly the protection `.json` had
    # before `REQUIRED_SUFFIXES` existed — none. Not hypothetical, and `.sh` is
    # the live candidate: issue #254 added it to the TOKEN scanner (see
    # `_iter_scanned_source_files`) and did NOT add it here.
    #
    # THE CASE FOR ADDING IT HERE NOW EXISTS, and #254 is what made it — saying
    # otherwise would repeat the mistake that change is about. That change moved
    # ~37 lines of hand-written English into `hooks/probe-python.sh` on the stated
    # argument that prose in an unscanned file is a leak surface. That argument
    # does not stop at project tokens: prose about hook WIRING is exactly the
    # prose that would spell `.claude/plugins/cla/hooks/...`, which is this
    # scanner's whole subject.
    #
    # DECLINED, for now, with the reason rather than by omission. The file
    # carries no such literal today — `grep -c '\.claude/plugins/cla'
    # .claude/plugins/cla/hooks/probe-python.sh` prints 0 — so this is a gap, not
    # a live defect, and the suffix would be this scanner's fifth for one file.
    # What tips it is the SHAPE of the risk, not its size: the token scanner's
    # widening was forced by prose that had already moved, while here nothing has
    # moved yet. Revisit the moment that grep returns non-zero, or the moment any
    # second `.sh` ships.
    #
    # Should it ever be added, it is one file against a floor margin of one — so
    # the count could not see it dropped again, and only this assertion plus a
    # `REQUIRED_SUFFIXES` entry would.
    #
    # Containment, not equality of the reached set — so this stays independent of
    # the filesystem and does not re-introduce the tautology.
    undeclared = sorted(set(SCANNED_SUFFIXES) - REQUIRED_SUFFIXES)
    assert not undeclared, (
        f"suffix(es) scanned but not declared required: {undeclared}. Add them to "
        f"REQUIRED_SUFFIXES, or nothing will notice them being removed again."
    )


def test_every_required_root_is_actually_reached():
    """The other axis, and the one that had a single assertion for five roots.

    `agents/` was pinned by name and the other four were not, so dropping
    `output-styles` (1 file) or `lib` (2 files) left 102 or 101 files against a
    floor of `>= 102`... which is only true since the floor moved. It used to be
    `>= 98`, and both drops passed every assertion in this file. Same two
    directions as the suffix pair directly above, for the same reasons."""
    by_root: dict[str, int] = {}
    for root_name, _path in _scanned_files_by_root():
        by_root[root_name] = by_root.get(root_name, 0) + 1
    absent = sorted(REQUIRED_ROOTS - set(by_root))
    assert not absent, (
        f"root(s) this scanner must reach but does not: {absent}. Either a root "
        f"was dropped from SCANNED_ROOTS, or the directory left the plugin, or "
        f"it holds no file of any scanned suffix. All three shrink the scan "
        f"silently — per-root counts: {dict(sorted(by_root.items()))}"
    )
    # And the direction the line above cannot see, exactly as `undeclared` is for
    # suffixes: a root ADDED to the scan without being declared required carries
    # no protection at all against being removed again.
    undeclared = sorted(set(SCANNED_ROOTS) - REQUIRED_ROOTS)
    assert not undeclared, (
        f"root(s) scanned but not declared required: {undeclared}. Add them to "
        f"REQUIRED_ROOTS, or nothing will notice them being removed again."
    )


def test_the_replacement_is_actually_in_use():
    """Non-vacuity partner with teeth: the guard passing because every reference
    was DELETED rather than converted would be a silent regression of its own.

    Counts REFERENCES, not files carrying at least one. The file count is the
    wrong unit for the sentence above, and by a wide margin: there are several
    times more references than carrying files (the printer line quoted below
    reports both). So a change deleting all but one reference per file would
    hold a file-count assertion green while the great majority of references
    vanished — a floor measuring something adjacent to what its docstring
    claims, which reads as coverage and is not.

    THE RATIO IS THE ARGUMENT, so the figures are not restated here. They live
    in the quoted printer line, which `test_the_recorded_counts_are_the_real_
    ones` checks against the tree; prose restating them is a second copy that
    nothing pins, and this exact pair has already drifted once.
    """
    occurrences = sum(
        p.read_text(encoding="utf-8", errors="replace").count("${CLAUDE_PLUGIN_ROOT}")
        for p in _scanned_files()
    )
    # The real count comes from the same printer as the floor above, and is
    # QUOTED rather than restated — a number written out in prose beside this
    # line would be a second copy that `_PRINTER_LINE` cannot see:
    #
    #     $ python plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py
    #     scanned 102  .json 3  .md 69  .mjs 1  .py 29  placeholder-refs 233 in 53 files
    #
    # The file-count version sat at 34 under a comment claiming 36 while the real
    # figure was 48 — fourteen of headroom, found by running that printer for the
    # first time. Same decorative-floor defect as the scan floor above, in the
    # neighbouring function, which is the argument for the printer existing
    # rather than the numbers being re-derived by hand.
    #
    # A one-below margin would be noise here: unlike the scan floor, this count
    # moves whenever prose is edited, and a doc consolidation legitimately
    # deletes several references at once. Pinned at 210 — close enough to catch
    # the wholesale deletion the docstring names, loose enough that ordinary
    # editing does not red the gate. That is a different rule from the scan
    # floor's, deliberately, because it counts a different kind of thing.
    #
    # 210 WAS EXAMINED WITH THE SCAN FLOOR AND DELIBERATELY NOT MOVED, which is
    # worth recording because the two rows want opposite treatment and the next
    # reader will see them side by side. When issue #246 re-derived the scan
    # floor from 98 to 102, this one stayed: its gap to the real count is the
    # rule rather than drift. Only the RECORD beside it was stale — it read 217
    # against a count that had long since moved past it — and that is the half
    # now pinned by
    # `test_the_recorded_counts_are_the_real_ones`. A stale record here misleads
    # whoever next decides whether 210 is still the right bound, which is the
    # only thing about this floor that was ever wrong.
    assert occurrences >= 210, (
        f"only {occurrences} ${{CLAUDE_PLUGIN_ROOT}} reference(s) in synced core; "
        "the cross-references skills need to invoke their own scripts appear to "
        "have gone missing rather than been converted"
    )


# The shape `__main__` prints, as a pattern, so the comments that QUOTE that
# output can be found and checked. Keep the two in step: widening the printer
# without widening this turns the check below off for the new field, and
# `test_the_recorded_counts_are_the_real_ones`'s non-vacuity assertion is what
# catches the cruder version of that mistake.
_PRINTER_LINE = re.compile(
    r"scanned (?P<scanned>\d+)\s+"
    r"\.json (?P<json>\d+)\s+\.md (?P<md>\d+)\s+\.mjs (?P<mjs>\d+)\s+\.py (?P<py>\d+)\s+"
    r"placeholder-refs (?P<refs>\d+) in (?P<ref_files>\d+) files"
)


def _live_printer_numbers() -> dict[str, int]:
    """What `__main__` prints, as a dict. ONE source for both."""
    files = list(_scanned_files())
    by_suffix = Counter(p.suffix for p in files)
    texts = [p.read_text(encoding="utf-8", errors="replace") for p in files]
    return {
        "scanned": len(files),
        "json": by_suffix[".json"],
        "md": by_suffix[".md"],
        "mjs": by_suffix[".mjs"],
        "py": by_suffix[".py"],
        # Both numbers, because both are cited: the floor pins occurrences, and
        # the file count is what makes the gap between them legible.
        "refs": sum(t.count("${CLAUDE_PLUGIN_ROOT}") for t in texts),
        "ref_files": sum(1 for t in texts if "${CLAUDE_PLUGIN_ROOT}" in t),
    }


def _printer_line() -> str:
    """The one place the printed line is FORMATTED.

    `__main__` calls this rather than recomputing, so the string a developer
    pastes into a comment and the numbers the test compares it against cannot
    come from two different computations. They could before: the printer built
    its own `Counter` and its own sums, so the checker could have agreed with
    the tree while disagreeing with the printer — a stale-record guard whose two
    halves are allowed to drift is the defect it exists to catch, one level up.
    """
    n = _live_printer_numbers()
    return (
        f"scanned {n['scanned']}  "
        f".json {n['json']}  .md {n['md']}  .mjs {n['mjs']}  .py {n['py']}  "
        f"placeholder-refs {n['refs']} in {n['ref_files']} files"
    )


def test_the_recorded_counts_are_the_real_ones():
    """The floors are hand-pinned; the RECORDED counts beside them are derived.

    WHY NOT DERIVE THE FLOORS TOO — the question this test's shape answers. A
    floor that re-derives itself asserts nothing: it moves to meet any collapse
    and passes. The floors must stay hand-pinned to mean anything. What decays is
    the *record* of what was measured, and the record is what misleads the next
    person deciding whether a floor is still right.

    THIS FILE IS THE WORKED EXAMPLE OF THAT DECAY, TWICE, and both times it was
    found by accident rather than by a check:

      * the scan floor sat at 95 under a comment claiming 96, against a real 99;
      * then at 98 under a comment claiming 99, against a real 103 — five files
        of headroom, in a file whose own rule calls a four-file margin "precisely
        the decorative floor the rule above forbids". That is what issue #246
        reported.

    The file has had a `__main__` throughout, precisely so the numbers could be
    re-derived. A printer nobody runs is not a defence; a test that runs it is.

    A deliberate addition trips this, and the fix is to paste the new printer
    output over the old — which is exactly the moment to ask whether the floor
    beside it should move too.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    quoted = list(_PRINTER_LINE.finditer(source))
    # Non-vacuity: if the printer's output format changes and the regex stops
    # matching, this test must fail rather than pass over zero lines.
    assert len(quoted) >= 2, (
        f"expected the printer's output quoted beside each floor, found "
        f"{len(quoted)}. If `__main__`'s format changed, update _PRINTER_LINE "
        f"and the quoted lines together — a regex that matches nothing turns "
        f"this guard off silently."
    )
    live = _live_printer_numbers()
    # THE PRINTER MUST ACCOUNT FOR EVERY FILE IT COUNTED. `_live_printer_numbers`
    # names its four suffix keys by hand, where the `__main__` it replaced derived
    # them from `sorted(by_suffix.items())` — so a FIFTH scanned suffix would be
    # counted in `scanned` and reported nowhere.
    #
    # Measured by adding `.sh` to SCANNED_SUFFIXES: the line becomes
    # `scanned 104  .json 3  .md 69  .mjs 1  .py 30 …`, whose suffix fields still
    # sum to 103. This test would go red on the moved total, someone would paste
    # the new line, and it would go green again with the `.sh` count never
    # recorded and never pinned — the silent narrowing `REQUIRED_SUFFIXES` exists
    # to prevent, reintroduced on the printer axis by the test meant to stop
    # records decaying.
    #
    # One assertion closes it, and it is a real check rather than a restatement:
    # both sides come from the same scan, but only the left is enumerated by hand.
    counted = live["json"] + live["md"] + live["mjs"] + live["py"]
    assert counted == live["scanned"], (
        f"the printer counted {live['scanned']} files but reports only {counted} "
        f"across its named suffixes — {live['scanned'] - counted} file(s) are "
        "scanned and shown nowhere. SCANNED_SUFFIXES has almost certainly grown: "
        "add the new suffix to `_live_printer_numbers`, `_printer_line` and "
        "`_PRINTER_LINE` together, then re-paste the quoted lines."
    )
    stale = []
    for match in quoted:
        recorded = {k: int(v) for k, v in match.groupdict().items()}
        if recorded != live:
            wrong = {k: (v, live[k]) for k, v in recorded.items() if v != live[k]}
            stale.append(
                f"  line {source[:match.start()].count(chr(10)) + 1}: "
                + ", ".join(f"{k} says {r} but is {a}" for k, (r, a) in wrong.items())
            )
    assert not stale, (
        "recorded measurement(s) in this file no longer match the tree. Re-run "
        "`python plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py` "
        "and paste its line over each stale one — then decide whether the floor "
        "beside it should move too:\n" + "\n".join(stale)
    )


if __name__ == "__main__":
    # The command this file's floors cite. It exists for the same reason the
    # sibling guard's does: `pytest <this file>` prints a pass count and nothing
    # else, so a floor whose stated measuring command emits no measurement
    # cannot be re-derived — and this file is the worked example of that decay,
    # twice over (see `test_the_recorded_counts_are_the_real_ones`).
    print(_printer_line())
