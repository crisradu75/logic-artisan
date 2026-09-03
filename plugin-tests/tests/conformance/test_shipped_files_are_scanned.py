"""Conformance guard: every shipped file is reached by a scanner, or is exempt
on purpose.

WHAT THIS CLOSES. Three scanners police the published plugin tree — the prose
and source token scans in `skills/_shared/scripts/check_no_project_tokens.py`,
and the hardcoded-install-path scan in `test_no_hardcoded_plugin_paths.py`. Each
is keyed on a root plus a file suffix, so a shipped file can fall outside all
three simply by being a new kind of file: a `.sh`, a suffix-less hook, a manifest
outside every scan root. Nothing failed when that happened, because "no scanner
opened it" and "a scanner opened it and found nothing" produce the identical
result — a clean run.

The coverage split was therefore recorded in PROSE, as a count, in CLAUDE.md and
in `check_no_project_tokens.py`'s own comments. That count went stale while
nothing noticed, which is the defect issue #178 actually names: a measurement
with no re-derivation mechanism decays into a claim, and this one carries a
scanner-coverage guarantee.

WHAT IT ASSERTS. `git ls-files` over the published directory is the definition of
"shipped" — the marketplace `git-subdir` source publishes the tracked tree
verbatim, with no exclusion field. Every tracked file must either be yielded by
one of the three real scanners, or appear in `EXEMPT` below with a reason. So
adding an unscanned file is a decision someone writes down, not an accident
nobody sees.

WHY THE ITERATORS ARE IMPORTED AND NOT RESTATED. This guard's whole subject is
which files the scanners actually open. A second copy of that rule here would
drift from the first, and the drift would be invisible in exactly the way the
original defect was. So it calls `_iter_scanned_files`, `_iter_scanned_source_files`
and `_scanned_files` directly. Changing any of their signatures breaks this file,
which is intended.

WHY IT IS A PYTEST GUARD AND DOES NOT SHIP. Its subject is the plugin's own
source tree, and it needs `git ls-files` against this repository. A consuming
repo has no tracked plugin tree of its own — it has a version-keyed cache
directory — so there is nothing here for it to check.

STALENESS CUTS BOTH WAYS. An `EXEMPT` entry naming a file that no longer ships,
or one a scanner has since grown to reach, fails too. An exemption that outlived
its reason is the same decayed claim in a new place.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLUGIN_ROOT = _REPO_ROOT / ".claude" / "plugins" / "cla"
_PUBLISHED_PREFIX = ".claude/plugins/cla"

# Shipped files no scanner opens, each with the reason it is not an accident.
# Keep this list short and argued. It is the pressure valve that could quietly
# empty this guard if it grew without one — the same role `_EXEMPT` plays in
# `tests/consistency/test_guards_have_mutant_batches.py`.
#
# FOUR of the five are clean today; the fifth is not, and an earlier version of
# this comment said all five were. Measured, both halves, rather than reasoned:
#
#   $ cd .claude/plugins/cla
#   $ grep -c '\.claude/plugins/cla' .claude-plugin/plugin.json .gitattributes \
#         hooks/git/pre-push hooks/probe-python.sh README.md
#     ...:0  ...:0  ...:0  ...:0  README.md:1        <- README.md:183
#   $ grep -rn 'C:\\Users\\' <the same five>          <- no match
#
# So `README.md` DOES carry the literal the hardcoded-path rule looks for, in
# the "Layout" code block. Widening that scanner to cover the plugin root — which
# the previous wording invited as safe — fails immediately. The absolute paths in
# `probe-python.sh` are generic (`$HOME/AppData/…`, `/usr/local/bin/…`) and match
# neither rule.
#
# This is CLAUDE.md check 3 (search for counterexamples, not just supporting
# cases) failing inside the one change whose entire thesis is that hand-written
# claims decay. Kept as the worked example rather than quietly corrected.
EXEMPT: dict[str, str] = {
    ".claude-plugin/plugin.json":
        "outside every scan root; the manifest is validated by "
        "tests/consistency/test_marketplace_manifest.py instead",
    ".gitattributes":
        "outside every scan root; carries line-ending rules, no prose or code",
    "README.md":
        "the plugin's own root README, exempt for TWO independent reasons. Its "
        "install commands legitimately name this repository, which is what makes "
        "them copy-pasteable — so scanning it for project tokens would flag the "
        "one file whose whole job is to identify the source. Separately, its "
        "Layout block spells the literal `.claude/plugins/cla` (line 183), so it "
        "would fail the hardcoded-path rule as well",
    "hooks/git/pre-push":
        "inside a scan root, but has NO suffix, so every suffix-keyed scanner "
        "skips it. Watched by hand; also covered behaviourally by "
        "tests/consistency/test_pre_push_is_installed.py. Issue #190 decided to "
        "keep it exempt: reaching it needs a rule not keyed on suffix at all, "
        "and it has no demonstrated leak to justify one",
    "hooks/probe-python.sh":
        "inside a scan root, but `.sh` is a suffix no scanner opens. Adding it "
        "would be the path scanner's fifth suffix and the token scanner's "
        "fourth (`.py`, `.json`, `.md`). Issue #190 decided against it: the "
        "absolute paths it does carry are generic ($HOME/..., /usr/local/...) "
        "and match neither the hardcoded-path rule nor the developer-path one",
}

# The SECOND split, and the one that decayed first. `EXEMPT` above asks "does
# ANY scanner open this file"; a file can pass that and still be outside the two
# TOKEN scanners, which are the ones enforcing the fact/procedure separation.
# `skills/_shared/README.md` is exactly that shape: the hardcoded-path scanner
# reaches it, so it is not in `EXEMPT`, while neither token scanner does.
#
# That distinction was recorded by hand in CLAUDE.md and in
# `check_no_project_tokens.py`'s own comments, in both places as a list and a
# count. Deriving it here is what keeps a later rename from silently falsifying
# both: move `skills/_shared/README.md` under a `references/` ancestor and the
# prose scanner starts reaching it, which fails this map rather than nothing.
#
# SCOPE: every shipped file that is not already in `EXEMPT`. There is no suffix
# rule here, and the first version's `.md`/`.py` scoping was a hole rather than a
# simplification. Its stated justification — "every other suffix is `EXEMPT`'s
# business" — is false, because `EXEMPT` catches only files NO scanner opens. A
# file the path scanner reaches but neither token scanner does satisfies neither
# map's condition and was reported by nothing.
#
# Not hypothetical. Measured: four shipped files were in exactly that state —
# `hooks/hooks.json`, both `required-permissions*.json`, and
# `mechanical-checks.mjs`. The `.json` pair already carries English prose in its
# `_comment` keys, which is precisely where a project token leaks; the guard's
# own failure text calls that state "outside the fact/procedure guarantee
# entirely" while staying green on it.
#
# Dropping the suffix rule makes the whole gap visible and forces a reason per
# file. It did NOT widen `check_no_project_tokens.py` — a behaviour change to a
# shipped guard, and a separate decision, which issue #190 then took. That
# decision widened the token scanners to `.json` and left `.sh`, the suffix-less
# `hooks/git/pre-push`, and `.mjs` exempt-with-a-reason, on the grounds that only
# the `.json` pair had a real leak surface. The three `.json` entries that used
# to sit below were deleted by that change; this guard's `now_covered` branch is
# what named them, which is the mechanism working rather than a courtesy.
# `.claude-plugin/plugin.json` was not affected: it is outside every scan root
# and stays in `EXEMPT`.
# `README.md` is deliberately absent: it is in `EXEMPT`, so it is not a candidate
# here, and listing it in both maps made this guard's own dead-entry branch fire.
# The guard caught that on the first run after the scope changed — which is the
# behaviour, not an inconvenience.
TOKEN_EXEMPT: dict[str, str] = {
    "skills/_shared/README.md":
        "sits directly under a skills subdirectory rather than beneath a "
        "`references/` ancestor, so the prose scanner's rule misses it, and the "
        "source scanner takes `.md` only under `agents`/`output-styles`. Reached "
        "by the hardcoded-path scanner, which is why it is not in EXEMPT",
    "skills/project-review/scripts/mechanical-checks.mjs":
        "the plugin's one Node script. The token scanners take `.py` and `.json` "
        "anywhere under the scan roots plus `.md` under `agents`/`output-styles`, "
        "so `.mjs` is out of scope for them; the path "
        "scanner covers it, and its own behaviour is tested by "
        "plugin-tests/node/mechanical-checks.test.mjs. Left unscanned "
        "deliberately by issue #190, which widened only the suffix with a "
        "demonstrated leak surface",
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_TOKENS = _load(
    _PLUGIN_ROOT / "skills" / "_shared" / "scripts" / "check_no_project_tokens.py",
    "_cnpt_for_coverage",
)
_PATHS = _load(
    Path(__file__).with_name("test_no_hardcoded_plugin_paths.py"),
    "_tnhpp_for_coverage",
)


def _shipped() -> set[str]:
    """Every tracked file under the published directory, plugin-relative.

    `git ls-files` rather than a filesystem walk: tracked-ness is what the
    marketplace publishes, and a walk would also sweep up `__pycache__`, a local
    scratch file, or anything else untracked — inflating the set with files no
    consumer ever receives.
    """
    proc = subprocess.run(
        ["git", "ls-files", "-z", "--", _PUBLISHED_PREFIX],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    prefix = _PUBLISHED_PREFIX + "/"
    return {
        line[len(prefix):]
        for line in proc.stdout.split("\0")
        if line.startswith(prefix)
    }


def _token_reached() -> set[str]:
    """Every plugin-relative path one of the two TOKEN scanners opens."""
    reached: set[str] = set()
    for path in _TOKENS._iter_scanned_files(_PLUGIN_ROOT / "skills"):
        reached.add(path.relative_to(_PLUGIN_ROOT).as_posix())
    for path in _TOKENS._iter_scanned_source_files(_PLUGIN_ROOT):
        reached.add(path.relative_to(_PLUGIN_ROOT).as_posix())
    return reached


def _reached() -> set[str]:
    """Every plugin-relative path at least one of the three scanners opens."""
    reached = _token_reached()
    for path in _PATHS._scanned_files():
        reached.add(path.relative_to(_PLUGIN_ROOT).as_posix())
    return reached


def split_coverage(
    shipped: set[str], reached: set[str], exempt: dict[str, str]
) -> tuple[list[str], list[str], list[str]]:
    """Partition the shipped set against the scanners and the exemption list.

    Returns `(unexplained, vanished, now_covered)`:

      * `unexplained` — shipped, reached by nothing, not exempt. The defect this
        guard exists for.
      * `vanished` — exempt, but no longer shipped. A dead entry.
      * `now_covered` — exempt, but a scanner has since grown to reach it. The
        exemption is stale and its reason is no longer true.

    Kept separate from the fixture plumbing above so it can be exercised on
    synthetic inputs, where all three branches are reachable — the real tree
    only ever exhibits the clean one.
    """
    unscanned = shipped - reached
    unexplained = sorted(unscanned - set(exempt))
    vanished = sorted(name for name in exempt if name not in shipped)
    now_covered = sorted(name for name in exempt if name in shipped & reached)
    return unexplained, vanished, now_covered


def test_every_shipped_file_is_scanned_or_deliberately_exempt():
    shipped, reached = _shipped(), _reached()
    unexplained, vanished, now_covered = split_coverage(shipped, reached, EXEMPT)

    problems: list[str] = []
    if unexplained:
        problems.append(
            f"{len(unexplained)} shipped file(s) that NO scanner opens and that "
            f"are not in EXEMPT. Either widen a scanner's roots/suffixes, or add "
            f"the file to EXEMPT with the reason it is safe unscanned:\n"
            + "\n".join(f"    {name}" for name in unexplained)
        )
    if vanished:
        problems.append(
            f"{len(vanished)} EXEMPT entr(y/ies) naming a file that no longer "
            f"ships. Delete the line — a stale exemption is the decayed claim "
            f"this guard exists to prevent:\n"
            + "\n".join(f"    {name}" for name in vanished)
        )
    if now_covered:
        problems.append(
            f"{len(now_covered)} EXEMPT entr(y/ies) that a scanner now reaches. "
            f"The exemption's reason is no longer true; delete the line:\n"
            + "\n".join(f"    {name}" for name in now_covered)
        )
    if problems:
        pytest.fail("\n\n".join(problems))


def test_every_shipped_file_is_token_scanned_or_deliberately_exempt():
    """The token scanners' own split, derived rather than written down.

    Same three failure modes as the guard above. The candidate set is every
    shipped file MINUS `EXEMPT` — not a suffix whitelist, which left four files
    satisfying neither map's condition and reported by nothing.
    """
    shipped = _shipped() - set(EXEMPT)
    unexplained, vanished, now_covered = split_coverage(
        shipped, _token_reached(), TOKEN_EXEMPT
    )

    problems: list[str] = []
    if unexplained:
        problems.append(
            f"{len(unexplained)} shipped file(s) that NEITHER token scanner "
            f"opens and that are in neither EXEMPT nor TOKEN_EXEMPT. A file here "
            f"is outside the fact/procedure guarantee entirely:\n"
            + "\n".join(f"    {name}" for name in unexplained)
        )
    if vanished:
        problems.append(
            f"{len(vanished)} TOKEN_EXEMPT entr(y/ies) naming a file that no "
            f"longer ships. Delete the line:\n"
            + "\n".join(f"    {name}" for name in vanished)
        )
    if now_covered:
        problems.append(
            f"{len(now_covered)} TOKEN_EXEMPT entr(y/ies) that a token scanner "
            f"now reaches. The exemption's reason is no longer true; delete the "
            f"line:\n" + "\n".join(f"    {name}" for name in now_covered)
        )
    if problems:
        pytest.fail("\n\n".join(problems))


def test_the_coverage_split_is_not_vacuous():
    """`unexplained` is empty when nothing ships, which is what a broken
    `_shipped()` would produce — the same shape as a clean run.

    Floors sit ONE BELOW the real counts. Re-derive them with the command that
    actually PRINTS them — this module has a `__main__` for exactly that reason,
    because `pytest <this file>` reports `8 passed` and surfaces a count only on
    failure, so naming it was a measurement citing a command that produces no
    measurement::

        $ python plugin-tests/tests/conformance/test_shipped_files_are_scanned.py
        shipped 104  reached 99  token-candidates 99  token-reached 97

    That one-below margin is the rule
    `test_no_hardcoded_plugin_paths.py` states for its own floor, and the first
    version of this file broke it — floors of 100 and 95 let three files be
    deleted with nothing noticing, which is the silence the rule exists to deny.
    The next deliberate deletion is EXPECTED to trip these and get them lowered
    with it.

    A floor drifts UPWARD too, and that direction has no failing test to
    announce it. Widening a scanner raises a real count while every floor stays
    where it was, so the margin silently grows into the headroom this rule
    forbids. Issue #190 did exactly that: `token-reached` went 94 -> 97 in one
    commit and left the token floor five below its population, in the same
    change that wrote up the identical drift next door. **Re-run the printer and
    re-pin every floor whenever a scanner's reach changes** — the widening is
    the signal, since nothing else will be.
    """
    shipped, reached = _shipped(), _reached()
    token_candidates = shipped - set(EXEMPT)
    assert len(shipped) >= 103, f"shipped set collapsed to {len(shipped)} files"
    assert (
        len(shipped & reached) >= 98
    ), f"scanner coverage collapsed to {len(shipped & reached)} files"
    assert (
        len(token_candidates & _token_reached()) >= 96
    ), "token-scanner coverage collapsed to " \
       f"{len(token_candidates & _token_reached())} files"


def test_every_exemption_carries_a_reason():
    """An exemption with an empty reason is a file removed from the guard's reach
    with nothing written down, which is the accident this guard converts into a
    decision."""
    blank = sorted(
        name
        for mapping in (EXEMPT, TOKEN_EXEMPT)
        for name, why in mapping.items()
        if not why.strip()
    )
    assert not blank, f"exemptions with no stated reason: {blank}"


def test_an_unscanned_new_file_is_reported():
    unexplained, vanished, now_covered = split_coverage(
        shipped={"a.md", "hooks/new-thing.sh"},
        reached={"a.md"},
        exempt={},
    )
    assert unexplained == ["hooks/new-thing.sh"]
    assert (vanished, now_covered) == ([], [])


def test_an_exempted_new_file_is_accepted():
    unexplained, vanished, now_covered = split_coverage(
        shipped={"a.md", "hooks/new-thing.sh"},
        reached={"a.md"},
        exempt={"hooks/new-thing.sh": "a stated reason"},
    )
    assert (unexplained, vanished, now_covered) == ([], [], [])


def test_an_exemption_for_a_deleted_file_is_reported():
    unexplained, vanished, now_covered = split_coverage(
        shipped={"a.md"},
        reached={"a.md"},
        exempt={"gone.sh": "a stated reason"},
    )
    assert vanished == ["gone.sh"]
    assert (unexplained, now_covered) == ([], [])


def test_an_exemption_a_scanner_now_reaches_is_reported():
    unexplained, vanished, now_covered = split_coverage(
        shipped={"a.md", "b.sh"},
        reached={"a.md", "b.sh"},
        exempt={"b.sh": "a stated reason"},
    )
    assert now_covered == ["b.sh"]
    assert (unexplained, vanished) == ([], [])


if __name__ == "__main__":
    # The command the vacuity floors cite. It exists because `pytest <this file>`
    # prints a pass count and nothing else — a floor whose stated measuring
    # command emits no measurement cannot be re-derived, which is the decay this
    # whole guard exists to stop, one level up.
    _shipped_now, _reached_now = _shipped(), _reached()
    _candidates = _shipped_now - set(EXEMPT)
    print(
        f"shipped {len(_shipped_now)}  "
        f"reached {len(_shipped_now & _reached_now)}  "
        f"token-candidates {len(_candidates)}  "
        f"token-reached {len(_candidates & _token_reached())}"
    )
