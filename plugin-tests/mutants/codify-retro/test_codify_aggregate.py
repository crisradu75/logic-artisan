"""Mutation batch for test_codify_aggregate.py.

`codify_aggregate.py` computes the numbers a retro ACTS on — above all the
prevention rate, which SKILL.md reads against a `< 0.5` heuristic. Every mutant
below leaves a well-formed report carrying a different number, which is the whole
reason this aggregator is a script and not a paragraph of prose: a wrong rate is
indistinguishable from a right one at a glance.

**NONE OF THE DRIFT-PINNED FUNCTIONS IS MUTATED HERE.** `_git_toplevel`,
`_runs_dir`, `_load_records`, `_coerce_int`, `_load_ledgers`, `_window` and
`_fleet_roots` are byte-identical copies shared with `spec_to_pr_aggregate.py` and
`lib/`, policed by `check_script_drift.py`. Every mutant below is in logic unique
to this aggregator — `_usable_int`, the effectiveness block, `aggregate_provenance`,
and `main`'s fleet suppression.

**Mutants 2 and 3 are the two ways a rate lies, and they lie in opposite
directions.** Mutant 2 folds `not_exercised` into the denominator, so the rate can
be improved by growing the checklist — rewarding exactly the bloat the retro
exists to fight. Mutant 3 turns an EMPTY sample's `None` into `0.0`, so a window
that measured nothing gets a failing grade and the heuristic fires on no data.
Neither changes the shape of the output.

**DELIBERATELY NOT A MUTANT:** `elif n > 0:` -> `elif n >= 1:` in
`aggregate_provenance`. Over integers these agree on every input — a no-op dressed
as a mutant. (`n > 0` -> `n >= 0` IS killable and is a legitimate alternative if a
second provenance mutant is ever wanted.)

**Coverage gaps, recorded because a mutant cannot fix them:** bare `--fleet` with
no path is never exercised; a malformed `maintenance.failure_modes_bullets` value
has no test (only the whole-block-non-dict case); and unlike its spec-to-pr
sibling this guard has no ledger-dedupe or out-of-order-window test, so those
behaviours are pinned only by the sibling's tests plus the drift guard, not here.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/codify-retro/test_codify_aggregate.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

SCRIPT = PLUGIN / "skills" / "codify-retro" / "scripts" / "codify_aggregate.py"

TARGETS = [DEV / "tests" / "skills" / "codify-retro" / "test_codify_aggregate.py"]

MUTANTS = [
    (
        # `isinstance(True, int)` is True in Python, which is exactly why the
        # explicit bool exclusion is there. Without it a record whose only
        # "count" is `true` is admitted as a contributor.
        "the effectiveness probe accepts a bool as a count, so a record that "
        "contributed nothing is counted into the sample it is measured against",
        SCRIPT,
        "    return isinstance(value, int) and not isinstance(value, bool)",
        "    return isinstance(value, int)",
        TARGETS,
    ),
    (
        "not_exercised is folded into the prevention denominator, so the outcome "
        "rate can be raised by growing the checklist rather than by preventing anything",
        SCRIPT,
        "    exercised = prevented + re_offended",
        '    exercised = prevented + re_offended + eff.get("not_exercised", 0)',
        TARGETS,
    ),
    (
        "an empty sample's rate becomes 0.0 instead of None, so a window that "
        "measured nothing gets a failing grade and the `< 0.5` heuristic fires on it",
        SCRIPT,
        '            "prevention_rate": round(prevented / exercised, 2) if exercised else None,',
        '            "prevention_rate": round(prevented / exercised, 2) if exercised else 0.0,',
        TARGETS,
    ),
    (
        # The stderr warning survives, which is the point: a metric computed over
        # half the records reads exactly like one computed over all of them.
        "container-shape drift stops being tallied, so a count block arriving as "
        "a list warns on stderr and reaches no counter",
        SCRIPT,
        "        drifted.add(key)",
        "        pass  # warned on stderr, that will do",
        TARGETS,
    ),
    (
        "rows predating the trailer field are scored as failures, so measurement "
        "adoption falls the further back in history you look",
        SCRIPT,
        "            no_field += 1",
        "            unmeasured += 1",
        TARGETS,
    ),
    (
        # An off-by-one rather than a deletion, deliberately: it is the shape a
        # "fleet means three or more, surely" edit would actually take.
        "the fleet suppression threshold slips by one, so a two-repo fleet reports "
        "one repo's per-repo fields as if they were the fleet's",
        SCRIPT,
        '    if len(ledgers) > 1 and "maintenance" in result:',
        '    if len(ledgers) > 2 and "maintenance" in result:',
        TARGETS,
    ),
]
