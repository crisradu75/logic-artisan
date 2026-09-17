"""Mutation batch for test_spec_to_pr_aggregate.py.

This aggregator's output is what a retro proposes orchestrator changes FROM, so
the expensive failures are the ones that make a producer bug look like a
behavioural finding, or vice versa. Mutants 1, 2 and 6 are all that shape: each
leaves a plausible report in which drift and signal have swapped places.

**NONE OF THE DRIFT-PINNED FUNCTIONS IS MUTATED HERE.** `_git_toplevel`,
`_runs_dir`, `_load_records`, `_coerce_int`, `_load_ledgers`, `_window` and
`_fleet_roots` are byte-identical copies shared with `codify_aggregate.py` and
`lib/`, policed by `check_script_drift.py`. Everything below is in this
aggregator's own code — `_normalize_agent`, `_tally_agents`, the Review pair
check, the findings reader, the cap block and `RETIRED_AGENT_KEYS`.

**Mutant 6 is the one worth reading the killing test for.** Charging a RETIRED
agent name as producer drift pins `shape_drift_records` permanently above zero —
a standing alarm nobody reads, which is worse than no alarm. The test that kills
it defends a DISTINCTION (history vs drift) rather than a count, and both halves
of its argument fail under the mutant, which is the right shape.

**DELIBERATELY NOT MUTANTS, and the first is a coverage finding in its own
right:**

  * `cap > 1` -> `cap > 0` in the exhaustion block. **No fixture anywhere carries
    `rounds_cap: 1`**, so the mutated and original expressions agree on every
    input the suite supplies. The `cap > 1` rule exists so Review never
    false-alarms the >=30% exhaustion rule — a number the retro acts on — and it
    is guarded by nothing. That is the most valuable gap this batch found and a
    mutant cannot close it; a fixture can.
  * `used == cap` -> `used >= cap`. Same cause: no fixture has `used > cap`.

**More gaps, recorded:** `warn_reasons`' `most_common(10)` truncation is untested
(no fixture has 11 distinct reasons), so the documented "top 10" is unpinned;
`deferred_to_todo_total` is never asserted as a positive sum; and a
`revise_findings_by_tier` whose keys are ONLY retired names is counted as legacy
rather than history, which no test states either way.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/spec-to-pr-retro/test_spec_to_pr_aggregate.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

SCRIPT = PLUGIN / "skills" / "spec-to-pr-retro" / "scripts" / "spec_to_pr_aggregate.py"

TARGETS = [
    DEV / "tests" / "skills" / "spec-to-pr-retro" / "test_spec_to_pr_aggregate.py"
]

MUTANTS = [
    (
        # The harm stays visible in the killing test: the phase still joins the
        # denominator and can never be a hit, so the rate is depressed with
        # nothing said about why.
        "an absent rounds_cap stops being counted as drift, so a phase with no cap "
        "joins the exhaustion denominator and silently depresses the rate",
        SCRIPT,
        '                    drifted_fields.add("rounds_cap")',
        "                    pass  # absence is fine",
        TARGETS,
    ),
    (
        # Inverting rather than deleting is what makes this worth more than a
        # removal: it fails from BOTH sides — honest records read as
        # contradictions and contradictory ones read as consistent.
        "the Review size-gate/agents pair check is inverted, so a producer "
        "emitting `small` WITH agents reads as consistent and every honest record does not",
        SCRIPT,
        '                    if (size_gate == "large") != has_agents:',
        '                    if (size_gate == "large") == has_agents:',
        TARGETS,
    ),
    (
        # The underscore replace is kept, so the legacy-severity test still
        # passes — which is the point of keeping the two replaces separable.
        "the colon spelling stops normalising, so a real agent's yield is filed "
        "as producer drift instead of counted",
        SCRIPT,
        '    return key.replace("_", "-").replace(":", "-")',
        '    return key.replace("_", "-")',
        TARGETS,
    ),
    (
        # The `continue` is kept, so this is a pure double-count rather than a
        # structural break — dispatch frequency inflates on a producer bug and
        # the duplicate is never reported.
        "agents stop being deduped within one dispatch, so a repeated agent "
        "credits twice and the duplicate is never warned about",
        SCRIPT,
        "            duplicates.append(agent)",
        "            target_counter[agent] += 1",
        TARGETS,
    ),
    (
        # The `phantom` clamp one line below is deliberately left intact so the
        # failure names exactly one field.
        "the negative-count clamp is dropped, so a stray negative `found` drags "
        "an agent's cumulative yield below its true total",
        SCRIPT,
        '                        revise_findings[agent]["found"] += max(0, found or 0)',
        '                        revise_findings[agent]["found"] += found or 0',
        TARGETS,
    ),
    (
        "a retired agent name becomes drift again, pinning shape_drift_records "
        "permanently above zero — the standing alarm nobody reads",
        SCRIPT,
        '    "skill-doc-reviewer", "skill-reviewer",',
        '    "skill-reviewer",',
        TARGETS,
    ),
]
