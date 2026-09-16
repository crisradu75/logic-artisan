"""Every site stating the mutation gate states the SAME mutation gate.

`openspec/specs/cla-plugin/spec.md`, "Review-fix evidence gate", requires that
every shipped markdown file stating the gate carry the killed-mutant clause: a kill
establishes that the suite reacts to that edit, not that the code or the test is
correct, so the killing assertion has to be read. Without a guard that is an
obligation asserted in a spec and enforced by nobody.

**This is not a hypothetical drift.** The gate text lived in two shipped skills,
`lite-pr/SKILL.md` and `spec-to-pr/references/revise.md`, and before the commit
that added the clause those two blocks were byte-identical except for one word
(`final report` vs `Handoff report`). Issue #193 named only one of them. A rule
added to the named site alone would have left the other briefing its reader
against a contract in which a kill is self-certifying — and nothing would have
said so, because each file reads correctly on its own. The defect is only visible
across files, which is exactly the shape a per-file review misses.

**Why the clause is matched by its load-bearing phrase rather than by a
paraphrase.** A presence check for the word "killed" passes on a block that
mentions killing mutants anywhere, which both sites did before the clause
existed. The phrase matched here is the instruction itself — read the killing
assertion — because that is the part a reader acts on, and a site that drops it
while keeping the surrounding prose is precisely the failure this guard exists
to catch.

The discovery set is derived, not hardcoded: a THIRD site stating the gate is
demanded the moment it appears, rather than being silently unpoliced the way a
hand-maintained file list would leave it. That happened: `multi-lite`'s step 7
enforcement round added a third site without the clause, and this guard was
the only check that noticed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"

# The gate's core instruction. A file stating this is telling its reader to run
# the mutation gate, whatever heading it sits under — which is why discovery
# keys on the procedure rather than on a section title a skill may not use.
_GATE_ANCHOR = "confirm it FAILS"

# The clause the spec requires alongside it. This is the actionable half: a site
# may say a great deal about mutants and still never tell the reader to read the
# assertion that killed one.
_REQUIRED_CLAUSE = "read the assertion that killed the mutant"

# Two sites carried the gate when this guard was written; multi-lite's step 7
# enforcement round (candidate-loop.md) became the third. The floor tracks the
# real population rather than sitting decoratively below it: a site DISAPPEARING
# is as much a defect as a site drifting, and a floor of 0 or 1 would pass on a
# tree where the gate had been deleted outright.
_KNOWN_SITE_COUNT = 3


def _gate_sites() -> list[Path]:
    """Every shipped markdown file that states the mutation gate."""
    return sorted(
        p
        for p in _PLUGIN_ROOT.rglob("*.md")
        if _GATE_ANCHOR in p.read_text(encoding="utf-8")
    )


def test_the_discovery_is_not_vacuous() -> None:
    """A guard whose collection is empty passes while checking nothing.

    This is the shape `test_guards_are_not_vacuous.py` catches statically for
    an asserted-empty collection; here the collection is built by a filesystem
    walk, so the floor has to be asserted against the population it really has.
    """
    sites = _gate_sites()
    assert len(sites) >= _KNOWN_SITE_COUNT, (
        f"{len(sites)} site(s) state the mutation gate, expected at least "
        f"{_KNOWN_SITE_COUNT}. Either the anchor {_GATE_ANCHOR!r} was reworded "
        f"(update it here in the same commit) or the gate was deleted from a "
        f"skill. Both need a human; neither may be fixed by lowering this floor."
    )


@pytest.mark.parametrize(
    "path",
    _gate_sites(),
    ids=lambda p: str(p.relative_to(_PLUGIN_ROOT)),
)
def test_every_gate_site_carries_the_killed_mutant_clause(path: Path) -> None:
    """The spec's "Every site stating the gate states the same contract"."""
    body = path.read_text(encoding="utf-8")
    assert _REQUIRED_CLAUSE in body, (
        f"{path.relative_to(_PLUGIN_ROOT)} states the mutation gate but omits "
        f"the killed-mutant clause ({_REQUIRED_CLAUSE!r}). A site without it "
        f"briefs its reader that a killed mutant is self-certifying, which the "
        f'spec\'s "Review-fix evidence gate" requirement forbids. Add the '
        f"clause here rather than removing this site from the gate."
    )
