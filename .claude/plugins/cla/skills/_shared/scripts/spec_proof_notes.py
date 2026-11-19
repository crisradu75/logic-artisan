"""The `manual:` and `waiting:` notes of a change's tasks, and what a scenario marker proves.

For `check_spec_proof.py`: a note in a change's `tasks.md` stands in for a test
that cannot run, and a scenario marker in a test file names the scenario it
proves. Both are read here as text; the entry point decides what a missing one
means. Not a command: import it, or run `check_spec_proof.py`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from spec_proof_parse import CheckerError


_NOTE = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:\[[ xX]\]\s+)?(?:\d+(?:\.\d+)*\.?\s+)?(manual|waiting):\s+(.+?)\s*$"
)
PROMPT_HALF = "(prompt half)"


@dataclass
class Note:
    kind: str  # "manual" | "waiting"
    heading: str | None  # None when it names no known heading
    raw: str
    change: str
    archived: bool
    prompt_half: bool
    spec: str | None = None  # the spec a `<spec> / <heading>` line names; None for the older heading-only form


def scan_notes(root: Path, known: set[str], universe: dict[str, set[str]] | None = None) -> list[Note]:
    """manual:/waiting: lines of every change's tasks.md. A line naming no known heading keeps heading None.

    A line is `<kind>: <spec> / <heading>: <reason>` (it covers that spec only: `universe` maps each spec to
    its headings) or the older `<kind>: <heading>: <reason>` (every spec of its change). The first form is
    tried first, and the longest name wins."""
    universe = universe or {}
    notes = []
    changes = root / "openspec" / "changes"
    if not changes.is_dir():
        return notes
    paths = sorted(changes.glob("*/tasks.md")) + sorted(changes.glob("archive/*/tasks.md"))
    for p in paths:
        archived = p.parent.parent.name == "archive"
        change = ("archive/" if archived else "") + p.parent.name
        try:
            lines = p.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise CheckerError(f"cannot read {p.relative_to(root).as_posix()}: {exc}") from exc
        for line in lines:
            m = _NOTE.match(line)
            if not m:
                continue
            body = m.group(2)
            if body.startswith("<"):
                continue  # a template placeholder in prose, not a note
            named = [(s, h) for s, hs in universe.items() for h in hs if body.startswith(f"{s} / {h}: ")]
            if named:
                spec, heading = max(named, key=lambda pair: len(pair[0]) + len(pair[1]))
            else:
                spec, heading = None, max((h for h in known if body.startswith(h + ": ")), key=len, default=None)
            notes.append(Note(m.group(1), heading, body, change, archived, PROMPT_HALF in body, spec))
    return notes


def resolve_scenario_marker(
    spec: str, rest: str, universe: dict[str, set[str]], owners: dict[str, dict[str, set[str]]], reqs: dict[str, set[str]]
) -> tuple[str | None, str]:
    """What a scenario marker ``scenario: <spec> / <rest>`` proves: (scenario heading, "") or (None, why not).

    ``rest`` is the two-part form's scenario heading, or the three-part form's ``<requirement> / <scenario>``.
    ``universe`` maps a spec to its scenario headings, ``owners`` a spec to each scenario's requirement headings
    and ``reqs`` a spec to its requirement headings (live specs and active deltas, as ``universe`` is).

    The whole of ``rest`` is read as a scenario heading (the two-part form), and ``rest`` is also split at each `` / ``
    (a requirement or scenario heading may hold one too) and the marker proves the scenario when some split
    names a requirement the scenario sits under. A split whose scenario exists but whose requirement does not
    hold it is a named problem, never "names no scenario". When MORE than one reading proves a scenario (the
    whole heading and a split, or two splits), the marker is ambiguous: which scenario it proves would depend on
    reading order, so it is a named problem that lists every reading rather than a silent pick of one."""
    scenarios = universe.get(spec, set())
    parts = rest.split(" / ")
    splits = [(" / ".join(parts[:i]), " / ".join(parts[i:])) for i in range(1, len(parts))]
    found = [(req, scn) for req, scn in splits if scn in scenarios]
    proving = [(req, scn) for req, scn in found if req in owners.get(spec, {}).get(scn, set())]
    readings = ([f"scenario {rest!r}"] if rest in scenarios else []) + [
        f"scenario {scn!r} under requirement {req!r}" for req, scn in proving
    ]
    if len(readings) > 1:
        return None, f"ambiguous: it reads as {'; '.join(readings)}; rename a heading so only one reading holds"
    if rest in scenarios:
        return rest, ""
    if proving:
        return proving[0][1], ""
    if not found:
        return None, "names no scenario in any live spec or active delta"
    # Prefer the split whose requirement exists, so the message says "wrong requirement" when it can.
    req, scn = next(((r, s) for r, s in found if r in reqs.get(spec, set())), found[0])
    held = ", ".join(repr(r) for r in sorted(owners.get(spec, {}).get(scn, set())))
    if req in reqs.get(spec, set()):
        return None, f"wrong requirement: scenario {scn!r} sits under {held}, not under requirement {req!r}"
    return None, f"unknown requirement: spec {spec!r} has no requirement {req!r} (scenario {scn!r} sits under {held})"
