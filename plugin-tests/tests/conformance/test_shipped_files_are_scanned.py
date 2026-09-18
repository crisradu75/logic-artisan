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
# THREE of the four are clean today; the fourth is not, and an earlier version
# of this comment said they all were. Re-measured from the repo root, both
# halves rather than reasoned:
#
#   $ grep -c '\.claude/plugins/cla' \
#         .claude/plugins/cla/.claude-plugin/plugin.json \
#         .claude/plugins/cla/.gitattributes \
#         .claude/plugins/cla/hooks/git/pre-push \
#         .claude/plugins/cla/README.md
#     ...:0  ...:0  ...:0  README.md:2       <- README.md:218 and :241
#
# THE DEVELOPER-PATH HALF IS NO LONGER A COMMENT. It is
# `test_the_unscanned_exemptions_carry_no_developer_path` below, which runs the
# shipped checker's own regexes over these files, paired with
# `test_the_detector_used_below_actually_detects` as its positive control. It was
# a `grep` in this comment for three generations and was wrong twice, which is
# why it moved into code.
#
# THE TRAP THAT BROKE IT, recorded so nobody re-derives the grep. No
# backslash-count is portable. In BRE `\\` is one literal backslash, so
# `'C:\\Users\\'` ends in a trailing backslash and GNU grep REFUSES it outright
# (`grep: Trailing backslash`, rc=2) — which reads as "no match" to anyone
# checking only the exit code. Doubling again to `'C:\\\\Users'` asks for two
# literal backslashes and cannot match a real path. Except that it DOES match
# under Git Bash, whose MSYS layer rewrites a path-shaped argument before grep
# sees it: `printf '%s' 'C:\\\\Users'` prints `C:\\Users`. Same command, vacuous
# on a POSIX shell and correct on this one — a measurement about the shell rather
# than about the tree, which is exactly what CLAUDE.md check 3's platform clause
# is about. A Python regex has no such layer, which is the other reason the check
# moved.
#
# So `README.md` DOES carry the literal the hardcoded-path rule looks for.
# Widening that scanner to cover the plugin root — which an older wording invited
# as safe — fails immediately.
#
# THE LIST WAS FIVE UNTIL ISSUE #254. `hooks/probe-python.sh` left it when the
# token scanner grew a `.sh` suffix, which it grew because that script became the
# declared home of the wiring rationale the plugin loader had rejected out of
# `hooks.json`. The entry's stated reason was "no demonstrated leak"; moving ~37
# lines of hand-written English in would have made that reason false while the
# line still read true, which is the exact decay this guard exists to catch. Its
# absolute paths were and are generic (`$HOME/AppData/…`, `/usr/local/bin/…`) and
# match neither path rule — the scanner run above is what says so now, rather
# than this comment.
#
# The stale-count defect is CLAUDE.md check 3 (search for counterexamples, not
# just supporting cases) failing inside the one change whose entire thesis is
# that hand-written claims decay. Kept as the worked example rather than quietly
# corrected — and note that the `README.md:1 / line 183` measurement it carried
# had itself gone stale by the time #254 re-ran it. THREE GENERATIONS OF THE SAME
# DEFECT NOW, which is the reason the pattern above is written the awkward way:
# the original claim was unmeasured, #254's re-measurement used a grep that
# cannot match a real path, and only a reviewer running it on a file that DOES
# carry one caught that. A grep whose negative result is its whole point needs a
# positive control in the same command, or it reports clean for having no teeth.
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
        "one file whose whole job is to identify the source. Separately, it "
        "spells the literal `.claude/plugins/cla` twice — once in prose about "
        "`--plugin-dir` and once in the Layout block — so it would fail the "
        "hardcoded-path rule as well",
    "hooks/git/pre-push":
        "inside a scan root, but has NO suffix, so every suffix-keyed scanner "
        "skips it. Watched by hand; also covered behaviourally by "
        "tests/consistency/test_pre_push_is_installed.py. Issue #190 decided to "
        "keep it exempt: reaching it needs a rule not keyed on suffix at all, "
        "and it has no demonstrated leak to justify one",
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
        "the plugin's one Node script. Neither token scanner opens `.mjs` — the "
        "prose one takes `SKILL.md`/`references/**/*.md` under `skills/`, and the "
        "source one takes `.py`/`.json`/`.sh` under the scan roots plus `.md` "
        "under `agents`/`output-styles` — so it is out of scope for both; the path "
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
        shipped 108  reached 104  token-candidates 104  token-reached 102

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
    the signal, since nothing else will be. Issue #254 widened the source token
    scanner to `.sh`, which moved `reached` 103 -> 104 and `token-reached`
    101 -> 102 (one file, `hooks/probe-python.sh`, which also left `EXEMPT` and
    so raised `token-candidates` 103 -> 104); both floors moved with it, in this
    commit, which is what that rule asks for rather than what it reports.
    """
    shipped, reached = _shipped(), _reached()
    token_candidates = shipped - set(EXEMPT)
    assert len(shipped) >= 107, f"shipped set collapsed to {len(shipped)} files"
    assert (
        len(shipped & reached) >= 103
    ), f"scanner coverage collapsed to {len(shipped & reached)} files"
    assert (
        len(token_candidates & _token_reached()) >= 101
    ), "token-scanner coverage collapsed to " \
       f"{len(token_candidates & _token_reached())} files"


def _developer_path_kinds(text: str) -> list[str]:
    """Which absolute-developer-path shapes `text` carries, by the SHIPPED rules.

    Calls the checker's own regexes rather than restating them, the same
    discipline `_token_reached` follows — a second copy here would drift from the
    scanner and the drift would be invisible.

    ALL THREE KINDS, and that sentence is load-bearing rather than descriptive.
    The first version of this function implemented two and omitted
    `MANGLED_WIN_PATH`, which made it a PARTIAL copy — exactly the drift the
    paragraph above says it exists to avoid, in the function that says it.
    Measured on `# see C:UsersaliceAppDataLocal for the cache`: the two
    implemented patterns both return None and the omitted one matches, with a
    non-placeholder user. A separator-stripped path in an exempt file — which is
    to say a file NO scanner opens — was therefore reported clean, and the
    checker's own comment names that shape as how a real developer username
    survived a previous sweep.

    Kept in `find_absolute_path_leaks`'s order and with its kind names, and each
    shape tested INDEPENDENTLY rather than as an `elif` chain, for the reason
    that function records: chaining let a line carrying a placeholder Windows
    path skip the home-path check entirely.
    """
    kinds: list[str] = []
    win = _TOKENS.WIN_ABS_PATH.search(text)
    if win and not any(h in win.group(0) for h in _TOKENS.PLACEHOLDER_PATH_HINTS):
        kinds.append("windows-drive-path")
    home = _TOKENS.HOME_ABS_PATH.search(text)
    if home and home.group(1).lower() not in _TOKENS.PLACEHOLDER_USERS:
        kinds.append("home-directory-path")
    mangled = _TOKENS.MANGLED_WIN_PATH.search(text)
    if mangled and not _TOKENS._starts_with_placeholder_user(mangled.group(1)):
        kinds.append("mangled-windows-path")
    return kinds


def test_the_detector_used_below_actually_detects():
    """The positive control, and it is not ceremony.

    Everything below asserts an ABSENCE across the exempt files, and an absence
    is what a detector that matches nothing also reports. This claim was carried
    in a comment as a `grep` for three generations and was wrong twice: first
    unmeasured, then re-measured with a BRE pattern whose backslash count meant
    two literal backslashes — which cannot match a real path, and whose rc=1
    therefore proved nothing. A reviewer running it against a file that DID carry
    a path is what surfaced that. The lesson is not "count backslashes more
    carefully"; it is that a negative result needs a positive control in the same
    run.

    ONE ASSERTION PER KIND, not one for the set. A control that exercises only
    the shapes already implemented cannot surface a MISSING shape — which is
    precisely what happened: the two-assertion version of this test passed while
    `_developer_path_kinds` silently omitted `MANGLED_WIN_PATH`, so the third
    class of leak went unreported in every exempt file. A control is only as wide
    as the thing it is written against, so it is written against the shipped
    checker's kind list instead.
    """
    win = r"prefix C:\Users\anna\foo suffix"  # path-fixture-ok
    assert _developer_path_kinds(win) == ["windows-drive-path"]
    assert _developer_path_kinds("see /home/anna/thing for it") == [
        "home-directory-path"
    ]
    # Separator-stripped — the shape a mangled scratchpad path collapses into,
    # and the one the two implemented patterns both miss.
    assert _developer_path_kinds(  # path-fixture-ok
        "# see C:UsersannaAppDataLocal for the cache"
    ) == ["mangled-windows-path"]
    # And the placeholder exemptions still hold, so the control does not pass by
    # reporting everything.
    assert _developer_path_kinds("see /home/me/thing") == []
    assert _developer_path_kinds(r"C:\Users\<name>\foo") == []


def test_the_unscanned_exemptions_carry_no_developer_path():
    """`EXEMPT` names the files NO scanner opens, so this is the only thing
    standing between one of them and an unnoticed absolute developer path.

    Scoped to the developer-path rule alone, deliberately: the install-path rule
    genuinely does not apply to `README.md`, whose whole job is to name this
    repository, and that difference is already argued per entry in `EXEMPT`. The
    developer-path rule has no such exception — a hardcoded `C:\\Users\\<name>`
    cannot be correct in any destination repo — so it applies to all four, which
    is what makes it checkable here rather than only arguable.
    """
    offenders: list[str] = []
    for name in sorted(EXEMPT):
        path = _PLUGIN_ROOT / name
        if not path.is_file():
            continue  # `vanished` is the other guard's business, not this one's
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if _TOKENS.ABS_PATH_EXEMPT_MARKER in line:
                continue
            for kind in _developer_path_kinds(line):
                offenders.append(f"{name}:{lineno} [{kind}] {line.strip()[:80]}")
    assert not offenders, (
        "exempt file(s) carry a hardcoded absolute developer path, which no "
        "scanner opens and which cannot be correct in any destination repo:\n"
        + "\n".join(f"    {o}" for o in offenders)
    )


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
