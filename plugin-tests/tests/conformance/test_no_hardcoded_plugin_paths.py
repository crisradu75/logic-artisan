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
#     .json 96 ['.json']   .mjs 98 ['.mjs']   .py 71 ['.py']   .md 32 ['.md']   None 99 []
#
# The `.mjs` row is the load-bearing one: 98 clears the floor, so only this
# assertion is left. Against the tautological version that column was `[]` in
# every row — which is what "it could not react" means, measured.
REQUIRED_SUFFIXES = frozenset({".md", ".py", ".mjs", ".json"})

# The same independent-expectation trick, one level up, for the ROOTS. Issue
# #246: `SCANNED_ROOTS` had five entries and only `agents/` was asserted, so
# four of five could silently stop being scanned.
#
# Measured before this list existed, by loading this module with one root removed
# from `SCANNED_ROOTS` and re-running every assertion `test_the_scan_is_not_vacuous`
# then made — the file floor, the lone `agents/` check, and the two suffix
# comparisons. Reproduce it by importing this file with `importlib`, reassigning
# `SCANNED_ROOTS`, and calling that test; against the floor of 98 it then had:
#
#     drop            files  >=98? missing required   refs  >=210?
#     skills             19  False ['.mjs']             14   False   caught
#     agents            101   True -                   231    True   caught
#     output-styles     102   True -                   234    True   SURVIVES
#     hooks              89  False -                   224    True   caught
#     lib               101   True -                   233    True   SURVIVES
#
# Only `skills` and `hooks` were caught, and both only INCIDENTALLY — by the
# file-count floor, which the comment on that floor prescribes lowering after a
# deliberate deletion. A floor lowered to 88 hands `hooks` a green run too. So
# four of the five were defended by arithmetic that is expected to move, and
# `agents` alone by a real assertion.
#
# `lib/` holds `log_run.py` and `ledger_summary.py`; `output-styles/` ships to
# every consuming repo. A hardcoded install path landing in either went
# unreported.
#
# WHY A SEPARATE LIST RATHER THAN "every root contributes a file". That version
# is the tautology `REQUIRED_SUFFIXES` above exists to avoid, one level up:
# `_scanned_files` iterates `SCANNED_ROOTS`, so deleting a root removes it from
# the declaration and from the file set in the same edit, and "every declared
# root contributed" stays true over the four that remain. It could not react to
# the one edit it would be added to catch.
REQUIRED_ROOTS = frozenset({"skills", "agents", "output-styles", "hooks", "lib"})

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"


def _scanned_files():
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
    # ORDER MATTERS HERE, and it is the opposite of the obvious one. The root and
    # suffix checks come BEFORE the file-count floor deliberately: with the floor
    # first, dropping `agents`, `hooks` or `lib` trips it at 101/89/101 and the
    # run reports "scan set collapsed", never reaching the assertion that names
    # WHICH root went missing. Measured — before this reorder only
    # `output-styles` (102 files, clearing the floor exactly) reached the root
    # check, so four of five failures were attributed to arithmetic that the
    # floor's own comment prescribes lowering. Specific assertion first, floor as
    # the backstop underneath it.
    #
    # Every REQUIRED root is actually reached, for the reason `REQUIRED_ROOTS`
    # states. This replaces a lone `agents/` assertion that left the other four
    # roots defended only by that floor — see issue #246 and the measured
    # drop-root table on that constant.
    reached_roots = {p.relative_to(_PLUGIN_ROOT).parts[0] for p in files}
    unreached = sorted(REQUIRED_ROOTS - reached_roots)
    assert not unreached, (
        f"root(s) this scanner must reach but does not: {unreached}. Either a "
        f"root was dropped from SCANNED_ROOTS, or its last scannable file left "
        f"the tree. Both shrink the scan silently."
    )
    # The other direction, exactly as for suffixes below: a root ADDED to
    # SCANNED_ROOTS without being declared required is reached, so the
    # assertion above stays green, and it carries none of the protection.
    undeclared_roots = sorted(set(SCANNED_ROOTS) - REQUIRED_ROOTS)
    assert not undeclared_roots, (
        f"root(s) scanned but not declared required: {undeclared_roots}. Add "
        f"them to REQUIRED_ROOTS, or nothing will notice them being removed again."
    )
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
    # but that is arithmetic, not a guarantee, and it has already been false
    # once: at a floor of 98 against 103 files the same drop left 100 and
    # cleared it, so between issue #190 and issue #246 this parenthetical
    # asserted a catch that was not happening. The comment above prescribes
    # lowering the floor on a deliberate deletion, and a floor lowered to 99
    # hands the `.json` narrowing a green run again. This assertion does not move.
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
    # before `REQUIRED_SUFFIXES` existed — none. Not hypothetical: the `EXEMPT`
    # entry for `hooks/probe-python.sh` in `test_shipped_files_are_scanned.py`
    # discusses adding `.sh` as this scanner's fifth suffix, and `probe-python.sh`
    # is one file against a floor margin of one, so the count could not see it
    # dropped again either.
    #
    # Containment, not equality of the reached set — so this stays independent of
    # the filesystem and does not re-introduce the tautology.
    undeclared = sorted(set(SCANNED_SUFFIXES) - REQUIRED_SUFFIXES)
    assert not undeclared, (
        f"suffix(es) scanned but not declared required: {undeclared}. Add them to "
        f"REQUIRED_SUFFIXES, or nothing will notice them being removed again."
    )
    # THE BACKSTOP, last on purpose — see the ordering note at the top of this
    # function. It catches a collapse the named lists above cannot describe: a
    # root still present and still contributing one file, every suffix still
    # reached, and ninety files gone from underneath.
    #
    # Re-measured with this file's own `__main__`, which is why it has one::
    #
    #     $ python plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py
    #     scanned 103  .json 3  .md 69  .mjs 1  .py 30  placeholder-refs 234 in 50 files
    #
    # The real count is 103. Pinned near it, not comfortably below it, matching
    # the rule `test_subprocess_encoding.py` states for its own floor: move it to
    # the new real count when something is deliberately added or deleted, never
    # to a number chosen to be safe from future deletions. That leaves a margin
    # of exactly one, which is the philosophy working as intended rather than a
    # defect to pad out: the next deliberate deletion is EXPECTED to trip this
    # floor and get it lowered along with it, so a false sense of headroom is
    # exactly what "pinned near it" is for this guard to not have.
    #
    # THIS FLOOR HAS NOW DRIFTED TWICE, which is why the number above is pinned
    # by `test_the_recorded_counts_are_the_real_ones` rather than left to the
    # next reader's diligence. First: a floor of 95 under a comment claiming 96
    # while the real count had risen to 99. Second (issue #246): 98 under a
    # comment claiming 99 while the real count had risen to 103 — five files of
    # headroom, precisely the decorative floor the rule above forbids. Both were
    # found by someone running the printer for an unrelated reason. A printer
    # nobody runs is not a defence; a test that runs it is.
    assert len(files) >= 102, f"scan set collapsed to {len(files)} files"


def test_the_replacement_is_actually_in_use():
    """Non-vacuity partner with teeth: the guard passing because every reference
    was DELETED rather than converted would be a silent regression of its own.

    Counts REFERENCES, not files carrying at least one. The file count is the
    wrong unit for the sentence above, and by a wide margin: 48 files carry 217
    occurrences, so a change deleting 169 of them while leaving one per file
    held the old assertion at 48 and green. It was insensitive to its own named
    failure by about 4.5x — a floor measuring something adjacent to what its
    docstring claims, which reads as coverage and is not.
    """
    occurrences = sum(
        p.read_text(encoding="utf-8", errors="replace").count("${CLAUDE_PLUGIN_ROOT}")
        for p in _scanned_files()
    )
    # Real count 234, from the same printer as the floor above:
    #
    #     $ python plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py
    #     scanned 103  .json 3  .md 69  .mjs 1  .py 30  placeholder-refs 234 in 50 files
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
    # SO THE GAP TO 234 IS NOT DRIFT AND 210 DOES NOT MOVE. Issue #246 reported
    # this floor alongside the scan floor's genuine drift; only the recorded
    # count above was stale (it read 217). The two rows want opposite treatment
    # and the distinction is the reason this paragraph exists. What IS pinned is
    # the recorded number, by `test_the_recorded_counts_are_the_real_ones` —
    # a stale record misleads whoever next decides whether 210 is still right.
    assert occurrences >= 210, (
        f"only {occurrences} ${{CLAUDE_PLUGIN_ROOT}} reference(s) in synced core; "
        "the cross-references skills need to invoke their own scripts appear to "
        "have gone missing rather than been converted"
    )


_PRINTER_LINE = re.compile(
    r"scanned (?P<scanned>\d+)\s+"
    r"\.json (?P<json>\d+)\s+\.md (?P<md>\d+)\s+\.mjs (?P<mjs>\d+)\s+\.py (?P<py>\d+)\s+"
    r"placeholder-refs (?P<refs>\d+) in (?P<ref_files>\d+) files"
)


def _live_printer_numbers() -> dict[str, int]:
    """What `__main__` below would print, as a dict. One source for both."""
    files = list(_scanned_files())
    by_suffix = Counter(p.suffix for p in files)
    texts = [p.read_text(encoding="utf-8", errors="replace") for p in files]
    return {
        "scanned": len(files),
        "json": by_suffix[".json"],
        "md": by_suffix[".md"],
        "mjs": by_suffix[".mjs"],
        "py": by_suffix[".py"],
        "refs": sum(t.count("${CLAUDE_PLUGIN_ROOT}") for t in texts),
        "ref_files": sum(1 for t in texts if "${CLAUDE_PLUGIN_ROOT}" in t),
    }


def test_the_recorded_counts_are_the_real_ones():
    """The floors are hand-pinned; the RECORDED counts beside them are derived.

    Why both, rather than deriving the floors too: a floor that re-derives
    itself asserts nothing — it would move to meet any collapse and pass. The
    floors must stay hand-pinned to mean anything. What decays is the *record*
    of what was measured, and that is what misleads the next person deciding
    whether a floor is still right.

    This file is the worked example of that decay, twice. The scan floor sat at
    95 under a comment claiming 96 against a real 99, then at 98 under a comment
    claiming 99 against a real 103 (issue #246). Both were found by someone
    running the printer for an unrelated reason. It has a `__main__` precisely so
    the numbers can be re-derived; the gap was that nothing ran it.

    So: this asserts every printer line quoted in this file's own comments still
    matches the tree. A deliberate addition trips it, and the fix is to paste
    the new printer output over the old — which is the moment to ask whether the
    floor beside it should move too.
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
    stale = []
    for match in quoted:
        recorded = {k: int(v) for k, v in match.groupdict().items()}
        if recorded != live:
            wrong = {k: (v, live[k]) for k, v in recorded.items() if v != live[k]}
            stale.append(f"  line {source[:match.start()].count(chr(10)) + 1}: "
                         + ", ".join(f"{k} says {r} but is {a}" for k, (r, a) in wrong.items()))
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
    # having sat at a floor of 95 under a comment claiming 96 while the real
    # count had risen to 99.
    from collections import Counter

    _files = list(_scanned_files())
    _by_suffix = Counter(p.suffix for p in _files)
    _texts = [p.read_text(encoding="utf-8", errors="replace") for p in _files]
    # Both numbers, because both are cited: the floor pins occurrences, and the
    # file count is what makes the gap between them legible.
    _refs = sum(t.count("${CLAUDE_PLUGIN_ROOT}") for t in _texts)
    _carrying = sum(1 for t in _texts if "${CLAUDE_PLUGIN_ROOT}" in t)
    print(
        f"scanned {len(_files)}  "
        + "  ".join(f"{suf} {n}" for suf, n in sorted(_by_suffix.items()))
        + f"  placeholder-refs {_refs} in {_carrying} files"
    )
