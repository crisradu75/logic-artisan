"""`multi-lite`'s merge policy and resume ledger are one contract spread over five files.

The policy is chosen at the Phase 1c gate (`candidate-extraction.md`), recorded in
the ledger header (`bootstrap-and-tracking.md`), acted on at step 8
(`candidate-loop.md`), summarised in the hoisted rules (`SKILL.md`), and reported
(`phase4-and-log.md`). Each file names the policy in its own prose, and nothing
compiles prose: a file that says `merge-each-clean` where another says
`merge-all-clean` reads fine to a human and leaves the orchestrator matching a
header value no step 8 branch recognises.

The resume half has the same shape. Step 2 decides whether an open PR still needs
merging by reading the ledger's `review` and `head_sha` columns. If the ledger
recipe stops declaring a column step 2 reads — or step 2 reads one the recipe
never writes — resume silently skips a clean PR the policy promised to merge.
"""

from __future__ import annotations

import re
from pathlib import Path

_SKILL = (
    Path(__file__).resolve().parents[3]
    / ".claude" / "plugins" / "cla" / "skills" / "multi-lite"
)
_REFS = _SKILL / "references"

POLICIES = {"merge-each-clean", "merge-dependencies-only"}

# Every file that states, records, acts on, or reports the policy.
_POLICY_FILES = [
    _SKILL / "SKILL.md",
    _REFS / "candidate-extraction.md",
    _REFS / "bootstrap-and-tracking.md",
    _REFS / "candidate-loop.md",
    _REFS / "phase4-and-log.md",
]

_CODE_SPAN = re.compile(r"`([^`\n]+)`")
# Two or more segments after `merge-`, as both policy names have. One segment is
# ordinary vocabulary in these files: `git merge-base`, a `merge-side` reason.
_POLICY_SHAPED = re.compile(r"(?<![A-Za-z0-9-])merge-[a-z]+(?:-[a-z]+)+")
_LEDGER_ROW = re.compile(r"`(id(?:\s*\|\s*[a-z_]+)+)`")


def _policy_tokens(text: str) -> set[str]:
    """Every policy-shaped name inside a code span.

    Scoped to code spans because that is how the policy is written wherever it is
    a value the run compares; prose like "merge per policy" is not a name.
    """
    return {
        tok
        for span in _CODE_SPAN.findall(text)
        for tok in _POLICY_SHAPED.findall(span)
    }


def _ledger_columns(text: str) -> list[str]:
    rows = _LEDGER_ROW.findall(text)
    assert len(rows) == 1, f"expected one ledger row declaration, found {rows}"
    return [c.strip() for c in rows[0].split("|")]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_every_policy_file_names_both_policies():
    missing = {
        path.name: sorted(POLICIES - _policy_tokens(_read(path)))
        for path in _POLICY_FILES
        if POLICIES - _policy_tokens(_read(path))
    }
    assert not missing, f"policy names missing: {missing}"


def test_no_policy_file_names_a_policy_that_does_not_exist():
    unknown = {
        path.name: sorted(_policy_tokens(_read(path)) - POLICIES)
        for path in sorted(_SKILL.rglob("*.md"))
        if _policy_tokens(_read(path)) - POLICIES
    }
    assert not unknown, f"unrecognised policy names: {unknown}"


def test_the_policy_scanner_is_not_vacuous():
    """A drifted name must be caught — otherwise the test above passes on anything."""
    text = "under `merge-all-clean` and `policy: <merge-each-clean | merge-before-dependents>`"
    assert _policy_tokens(text) == {
        "merge-all-clean", "merge-each-clean", "merge-before-dependents",
    }
    assert _policy_tokens(
        "run `gh pr merge 12 --squash`, `failed-merge`, `git merge-base --is-ancestor`"
    ) == set()


def _section(text: str, start: str, end: str) -> str:
    """The text between two markers, each required to occur exactly once.

    Presence anywhere in candidate-loop.md proves nothing: `head_sha` and `review`
    also appear in steps 6, 7 and 8, so deleting step 2's resume arms would leave
    a whole-file check green.
    """
    assert text.count(start) == 1, f"marker {start!r} not found exactly once"
    assert text.count(end) == 1, f"marker {end!r} not found exactly once"
    body = text.split(start, 1)[1].split(end, 1)[0]
    assert body.strip(), f"empty section between {start!r} and {end!r}"
    return body


_STEP_2 = ("2. **Resume check", "3. **Ensure the right base.**")
_STEP_3 = ("3. **Ensure the right base.**", "4. **Run `/cla:lite-pr`")
_STEP_8A = ("**8a. Should this candidate merge?**", "**8b. Pre-merge checks")
_STEP_8B = ("**8b. Pre-merge checks", "**8c. Merge, then confirm it landed.**")


def test_resume_reads_only_columns_the_ledger_declares():
    columns = _ledger_columns(_read(_REFS / "bootstrap-and-tracking.md"))
    loop = _read(_REFS / "candidate-loop.md")
    step_2 = _section(loop, *_STEP_2)
    # The columns step 2's resume decision itself branches on.
    for needed in ("status", "head_sha", "deferred", "review"):
        assert needed in columns, f"ledger row no longer declares `{needed}`"
        assert f"`{needed}`" in step_2, f"step 2 no longer reads `{needed}`"
    for needed in ("branch", "pr_number"):
        assert needed in columns, f"ledger row no longer declares `{needed}`"
    # Step 3 refuses a dependent whose dependency has no confirmed merge commit.
    assert "merge_commit" in columns
    assert "`merge_commit`" in _section(loop, *_STEP_3)


def test_resume_without_recorded_findings_is_never_clean():
    """`/cla:lite-pr` keeps deferred findings only in context. A resumed step 7
    that found none recorded would otherwise match "`deferred` is `0`" by
    default and merge a PR whose Critical finding nobody enforced."""
    step_2 = _section(_read(_REFS / "candidate-loop.md"), *_STEP_2)
    arm = next(
        (line for line in step_2.splitlines() if "`deferred` empty" in line), None
    )
    assert arm is not None, "step 2 has no arm for a row with no recorded findings"
    assert "`review: unresolved`" in arm
    assert "`review: clean`" not in arm


def test_step_8a_checks_merging_stopped_before_either_policy_says_yes():
    """A first-match reading must never reach a policy's "yes" after a host refusal."""
    step_8a = _section(_read(_REFS / "candidate-loop.md"), *_STEP_8A)
    stopped = step_8a.find("`merging stopped`")
    each = step_8a.find("**`merge-each-clean`**")
    deps = step_8a.find("**`merge-dependencies-only`**")
    assert -1 not in (stopped, each, deps)
    assert stopped < each < deps


def test_step_8a_does_not_swap_what_the_two_policies_merge():
    step_8a = _section(_read(_REFS / "candidate-loop.md"), *_STEP_8A)
    arm = {
        name: next(
            line for line in step_8a.splitlines() if f"**`{name}`**" in line
        )
        for name in POLICIES
    }
    assert "whether or not anything depends on it" in arm["merge-each-clean"]
    assert "only if" not in arm["merge-each-clean"]
    assert "only if" in arm["merge-dependencies-only"]


def test_every_merge_runs_the_full_gate_first():
    """`/cla:lite-pr` commits its review fixes after its own Test phase, so the
    full gate at 8b is the only full run a merged head gets."""
    step_8b = _section(_read(_REFS / "candidate-loop.md"), *_STEP_8B)
    assert "full Test gate" in step_8b


def test_the_ledger_row_parser_is_not_vacuous():
    assert _ledger_columns("a row `id | status | head_sha` here") == [
        "id", "status", "head_sha",
    ]


def _unrecorded_step_8_entries(text: str) -> list[str]:
    """Lines that send a candidate to step 8 without recording `review: clean`.

    Step 2 re-enters step 8 only for a row whose `review` is `clean`, so an arm
    that reaches step 8 without writing it produces a row resume cannot finish.
    Presence of the string anywhere is not enough: step 7 has two such arms.
    """
    return [
        line.strip()
        for line in text.splitlines()
        if "go to step 8" in line.lower() and "`review: clean`" not in line
    ]


def test_every_step_7_arm_into_step_8_records_review_clean():
    loop = _read(_REFS / "candidate-loop.md")
    assert len(re.findall(r"go to step 8", loop, re.IGNORECASE)) >= 2, (
        "step 7 no longer has its two arms into step 8; re-check this test's premise"
    )
    assert not _unrecorded_step_8_entries(loop)


def test_the_step_8_entry_scanner_is_not_vacuous():
    text = "- a → Write `review: clean` and go to step 8.\n- b → clean; go to step 8."
    assert _unrecorded_step_8_entries(text) == ["- b → clean; go to step 8."]


def test_both_review_values_are_written_and_read():
    loop = _read(_REFS / "candidate-loop.md")
    for value in ("clean", "unresolved"):
        assert f"`review: {value}`" in loop, f"step 7 never writes `review: {value}`"
        assert f"`review` is `{value}`" in loop, f"step 2 never reads `review` is `{value}`"
