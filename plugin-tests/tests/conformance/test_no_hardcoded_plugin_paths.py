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
    # Re-measured with this file's own `__main__`, which is why it has one::
    #
    #     $ python plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py
    #     scanned 99  .json 3  .md 67  .mjs 1  .py 28  using-placeholder 48
    #
    # The real count is 99. Pinned near it, not
    # comfortably below it, matching the rule `test_subprocess_encoding.py`
    # states for its own floor: move it to the new real count when something is
    # deliberately added or deleted, never to a number chosen to be safe from
    # future deletions. That leaves a margin of exactly one, which is the
    # philosophy working as intended rather than a defect to pad out: the next
    # deliberate deletion is EXPECTED to trip this floor and get it lowered
    # along with it, so a false sense of headroom is exactly what "pinned near
    # it" is for this guard to not have.
    #
    # It had drifted to a floor of 95 against a comment claiming 96, while the
    # real count had risen to 99 — four files of headroom, which is precisely
    # the decorative floor the rule above forbids.
    assert len(files) >= 98, f"scan set collapsed to {len(files)} files"
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
    # it. Today the floor happens to catch a `.json` drop (99 - 3 = 96 < 98),
    # but that is arithmetic, not a guarantee: the comment above prescribes
    # lowering the floor on a deliberate deletion, and a floor lowered to 96
    # hands the `.json` narrowing a green run. This assertion does not move.
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
    # Real count 217, from the same printer as the floor above:
    #
    #     $ python plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py
    #     scanned 99  .json 3  .md 67  .mjs 1  .py 28  placeholder-refs 217 in 48 files
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
    assert occurrences >= 210, (
        f"only {occurrences} ${{CLAUDE_PLUGIN_ROOT}} reference(s) in synced core; "
        "the cross-references skills need to invoke their own scripts appear to "
        "have gone missing rather than been converted"
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
