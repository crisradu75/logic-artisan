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

import subprocess
from collections import Counter
from pathlib import Path

import pytest

BAD = ".claude/plugins/cla"
# `hooks/` is scanned too, and so are `.py`/`.json`. The first version
# covered only `*.md` under three roots, which left the guard blind to exactly
# the surfaces that still held the literal path: a usage comment in a Node
# script (deleted 2026-10-08, and `.mjs` with it), one in `_dispatch_lib.py`,
# and anything in `hooks/hooks.json`. A guard that cannot see where the defect actually lives is
# a guard that reports clean.
SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")
SCANNED_SUFFIXES = (".md", ".py", ".json")

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
# THAT THIS ASSERTION FIRES IS ESTABLISHED BY A COMMAND, NOT BY A BATCH. No
# single-edit mutant isolates it: that needs a suffix with exactly one file that
# another scanner also reaches, and no such suffix exists. So it is measured
# directly instead::
#
#     $ python - <<'PY'
#     import importlib.util, pathlib
#     p = pathlib.Path("plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py")
#     def load():
#         s = importlib.util.spec_from_file_location("m", p.resolve())
#         m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
#     for drop in (".json", ".py", ".md", None):
#         m = load()
#         if drop:
#             m.SCANNED_SUFFIXES = tuple(x for x in m.SCANNED_SUFFIXES if x != drop)
#         files = list(m._scanned_files())
#         print(drop, len(files), sorted(m.REQUIRED_SUFFIXES - {f.suffix for f in files}))
#     PY
#     .json 97 ['.json']  .py 73 ['.py']  .md 30 ['.md']  None 100 []
#
# Against the tautological version that column was `[]` in every row — which is
# what "it could not react" means, measured. A `.mjs` row used to be the
# load-bearing one (one file, so dropping it cleared the old count floor and
# only this assertion was left). The floor is gone: `test_the_scan_is_not_vacuous`
# now compares the scan with `git ls-files`, filtered by this list, so dropping
# any suffix also leaves tracked files unscanned there. This assertion stays
# because it names the cause in one line.
REQUIRED_SUFFIXES = frozenset({".md", ".py", ".json"})

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
# (The measurements above are against the count floor that the `git ls-files`
# comparison in `test_the_scan_is_not_vacuous` replaced; that comparison, filtered
# by this list, also fails on either drop.)
REQUIRED_ROOTS = frozenset({"skills", "agents", "output-styles", "hooks", "lib"})

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"

# A floor on `_tracked_files_the_scan_must_reach`, not on the scan: 155 tracked files
# when it was set, so it sits far below them and no ordinary addition or deletion
# moves it. It only has to tell "the enumeration works" from "it matches nothing".
_MIN_TRACKED_FILES = 50


def _scanned_files_by_root():
    """`(root_name, path)` per scanned file — the root identity `_scanned_files`
    throws away at the yield.

    Kept as the primitive rather than as a change to `_scanned_files`'s return
    shape, so `_scanned_files`'s callers are unaffected."""
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


def _tracked_files_the_scan_must_reach() -> set[Path]:
    """What the scan is required to reach, enumerated WITHOUT the scanner.

    `git ls-files` under the plugin, kept to `REQUIRED_ROOTS` and
    `REQUIRED_SUFFIXES` (the independent lists above, not `SCANNED_ROOTS` and
    `SCANNED_SUFFIXES`), and to files present on disk, since an unstaged
    deletion is not there to scan. Tracked files only: the plugin ships what git
    tracks, and the scanner's `rglob` also reaches untracked files, which is why
    the test below asks for containment rather than equality.

    A git failure fails the test rather than skipping it. `plugin-tests/` never
    ships, so it always runs in a git checkout, and a skip here would be the
    vacuous pass this test exists to prevent.
    """
    try:
        listing = subprocess.run(
            ["git", "-C", str(_PLUGIN_ROOT), "ls-files", "-z", "--", "."],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.fail(f"cannot list the plugin's tracked files with git: {exc}")
    if listing.returncode != 0:
        pytest.fail(f"`git ls-files` failed under {_PLUGIN_ROOT}: {listing.stderr.strip()}")
    tracked = set()
    for rel in filter(None, listing.stdout.split("\0")):
        path = _PLUGIN_ROOT / rel
        if (
            Path(rel).parts[0] in REQUIRED_ROOTS
            and path.suffix in REQUIRED_SUFFIXES
            and path.is_file()
        ):
            tracked.add(path)
    return tracked


def test_the_scan_is_not_vacuous():
    """A guard that scans nothing passes forever, and two guards in this repo
    already did once.

    WHY THERE IS NO PINNED COUNT. This test used to assert `len(files) >= N`,
    with N pinned one below the real count and the printer's output line quoted
    beside it and checked by a second test. So every change that added or
    deleted a shipped file had to edit the same two lines, and parallel pull
    requests conflicted on them: five merges on 2026-11-19 alone. The pin was
    never the protection, only a proxy for it. The protection is that a
    narrowed scan fails, and this compares the scan with an enumeration that
    does not go through the scanner (`_tracked_files_the_scan_must_reach`), so
    a dropped root, a dropped suffix, or a pruning rule that skips a folder
    each leaves tracked files unscanned and fails here, whatever the count.

    The one number left is a floor on the enumeration itself, far below the
    real count, so an enumeration that matches nothing (a broken filter, a git
    that lists nothing) cannot make the comparison pass over an empty set. A
    deliberate addition or deletion never needs to touch it.
    """
    files = list(_scanned_files())
    required = _tracked_files_the_scan_must_reach()
    assert len(required) > _MIN_TRACKED_FILES, (
        f"`git ls-files` found only {len(required)} tracked file(s) the scan must reach, "
        f"expected more than {_MIN_TRACKED_FILES}: the enumeration has stopped matching, "
        "and the comparison below would pass over nothing"
    )
    unscanned = sorted(p.relative_to(_PLUGIN_ROOT).as_posix() for p in required - set(files))
    assert not unscanned, (
        f"{len(unscanned)} tracked file(s) under the required roots and suffixes are not "
        f"scanned, so a hardcoded path in them would go unseen: {unscanned[:20]}"
    )
    assert any(
        p.relative_to(_PLUGIN_ROOT).as_posix().startswith("agents/") for p in files
    ), "agents/ is not being scanned"
    # Every REQUIRED suffix is actually reached. Two directions, one assertion,
    # and `REQUIRED_SUFFIXES` above explains why the expectation is a separate
    # list rather than `SCANNED_SUFFIXES` itself.
    #
    # Direction one: a suffix removed from `SCANNED_SUFFIXES`. The tracked-file
    # comparison above fails on that too, since the enumeration filters on
    # `REQUIRED_SUFFIXES`; this assertion names the cause. It was once the only
    # defence: under the old count floor a suffix with fewer files than the
    # floor's margin dropped out unseen (`.mjs`, one file, did exactly that
    # until it was deleted), and `hooks/hooks.json` was covered here and nowhere
    # else until issue #190 widened the token scanner to `.json`.
    #
    # Direction two: the last file of a declared suffix leaving the TREE, which
    # the comparison above cannot see, since the file has left both sides.
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
    # Should it ever be added, it goes in `REQUIRED_SUFFIXES` too: that entry is
    # what makes the tracked-file comparison above, and this assertion, see it
    # dropped again.
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
    `output-styles` (1 file) or `lib` (2 files, then) left 102 or 101 files
    against a floor of `>= 98`, and both drops passed every assertion in this
    file. The count floor is gone; the tracked-file comparison in
    `test_the_scan_is_not_vacuous` now fails on either drop too, and this test
    names the root. Same two directions as the suffix pair directly above, for
    the same reasons."""
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
    times more references than carrying files (this file's `__main__` prints
    both). So a change deleting all but one reference per file would
    hold a file-count assertion green while the great majority of references
    vanished — a floor measuring something adjacent to what its docstring
    claims, which reads as coverage and is not.

    THE RATIO IS THE ARGUMENT, so the figures are not restated here: run the
    printer for them. A copy written into this file is a second record that
    every prose edit moves, and this exact pair has already drifted once.
    """
    occurrences = sum(
        p.read_text(encoding="utf-8", errors="replace").count("${CLAUDE_PLUGIN_ROOT}")
        for p in _scanned_files()
    )
    # The real count comes from the printer (`python
    # plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py`). It is
    # not quoted here: a quoted printer line, checked by a test, used to sit
    # beside this floor and the scan floor, and every change that added a
    # shipped file or edited a reference had to re-paste it, so parallel pull
    # requests conflicted on it (five merges on 2026-11-19). The scan floor was
    # replaced by a comparison with `git ls-files`; this floor stays a number,
    # because nothing independent enumerates references.
    #
    # The file-count version sat at 34 under a comment claiming 36 while the real
    # figure was 48 — fourteen of headroom, found by running that printer for the
    # first time.
    #
    # A one-below margin would be noise here: this count moves whenever prose is
    # edited, and a doc consolidation legitimately deletes several references at
    # once. The floor is set to catch the wholesale deletion the docstring names
    # and loose enough that ordinary editing does not red the gate, so it moves
    # only on a consolidation, never on an ordinary addition.
    #
    # It MOVED, to 204, when slim-spec-to-pr-retro deleted `retro-skeleton.md` and
    # cut the retro's SKILL.md to a fifth: exactly the doc consolidation the rule
    # above names, which took the real count from 214 to 208, under 210. The gap
    # it had (four) is kept. It moved again, to 198, when retire-unread-ledgers
    # deleted three skills' logging steps and the generic ledger reader: 208 to
    # 202, under 204, the gap of four kept. And to 178 when slim-spec-to-pr cut
    # spec-to-pr's SKILL.md and references to stubs: 199 to 182, under 198, the
    # gap of four kept. And to 172 when delete-mechanical-checks deleted the Node
    # script, project-review's command for it and that skill's resolver
    # paragraph: 183 to 176, under 178, a gap of four.
    assert occurrences >= 172, (
        f"only {occurrences} ${{CLAUDE_PLUGIN_ROOT}} reference(s) in synced core; "
        "the cross-references skills need to invoke their own scripts appear to "
        "have gone missing rather than been converted"
    )


def _live_printer_numbers() -> dict[str, int]:
    """What `__main__` prints, as a dict."""
    files = list(_scanned_files())
    by_suffix = Counter(p.suffix for p in files)
    texts = [p.read_text(encoding="utf-8", errors="replace") for p in files]
    return {
        "scanned": len(files),
        "json": by_suffix[".json"],
        "md": by_suffix[".md"],
        "py": by_suffix[".py"],
        # Both numbers: the reference floor pins occurrences, and the file
        # count is what makes the gap between them legible.
        "refs": sum(t.count("${CLAUDE_PLUGIN_ROOT}") for t in texts),
        "ref_files": sum(1 for t in texts if "${CLAUDE_PLUGIN_ROOT}" in t),
    }


def _printer_line() -> str:
    """The line `__main__` prints. Not quoted anywhere in this file, on purpose:
    see `test_the_scan_is_not_vacuous` for why the recorded copies were removed."""
    n = _live_printer_numbers()
    return (
        f"scanned {n['scanned']}  "
        f".json {n['json']}  .md {n['md']}  .py {n['py']}  "
        f"placeholder-refs {n['refs']} in {n['ref_files']} files"
    )


if __name__ == "__main__":
    # The measuring command for the reference floor. `pytest <this file>`
    # prints a pass count and nothing else, so a floor whose measuring command
    # emits no measurement cannot be re-derived.
    print(_printer_line())
