"""The requirement and scenario model `check_spec_proof.py` reads specs through.

Splits a spec's markdown into requirement blocks and proof units, reads delta
operations, and checks a spec's format. It touches no file and starts no
subprocess; the checker's entry point (`check_spec_proof.py`) owns those. Not a
command: import it, or run `check_spec_proof.py`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


FACTS_RELPATH = "cla.io/project-facts.md"

_H2 = re.compile(r"^##\s+(?!#)(.+?)\s*$")
_H3 = re.compile(r"^###\s+(?!#)")
# OpenSpec reads the keyword case-insensitively, so `### requirement:` must not dodge the counts.
_REQ = re.compile(r"^###\s+Requirement:\s*(.+?)\s*$", re.I)
_SCN = re.compile(r"^####\s+Scenario:\s*(.+?)\s*$", re.I)
_PURPOSE_H = re.compile(r"^##\s+Purpose\s*$", re.I)

_H4 = re.compile(r"^####\s+(?!#)")


def _fence_after(line: str, fence: tuple[str, int] | None) -> tuple[str, int] | None:
    """The code-fence state after `line`: None outside a fence, else (marker character, run length) of the open one.

    Same marker rules as `_fence_step` (not its blockquote and list handling): a run of 3 or more backticks (info string without a backtick) or tildes opens
    a fence; only a bare run of the SAME character at least as long closes it. A `~~~` line inside a ``` fence,
    a shorter run, or a run with an info string (```` ```python ````) is content, not a closer."""
    m = _FENCE_LINE.match(line)
    if fence is None:
        return (m.group(2)[0], len(m.group(2))) if _opens_fence(m) else None
    closes = m and m.group(2)[0] == fence[0] and len(m.group(2)) >= fence[1] and not m.group(3).strip()
    return None if closes else fence


def _req_name(name: str) -> str:
    """A requirement name as OpenSpec reads it (`normalizeRequirementName`): a closing run of `#` after a space
    or tab is not part of the name, so `Foo ##` is `Foo` while `C#` keeps its `#`. A name that is only a
    `#` run is empty. Scenario names are read the same way."""
    return re.sub(r"(?:^|[ \t]+)#+[ \t]*$", "", name).strip()


# A line that can open or close a fence: its indent, a run of 3 or more backticks or tildes, the rest.
_FENCE_LINE = re.compile(r"^([ \t]*)(`{3,}|~{3,})(.*)$")


@dataclass
class Unit:
    heading: str
    body: str


@dataclass
class SpecFile:
    rel: str
    spec: str
    kind: str  # "live" | "active" | "archived"
    change: str | None
    text: str
    units: list[Unit] = field(default_factory=list)


class CheckerError(Exception):
    """The checker cannot do its job (exit 2)."""


def _norm(lines: list[str]) -> str:
    return " ".join(" ".join(lines).split())


def parse_units(text: str, mode: str, delta: bool) -> list[Unit]:
    """Requirements (or scenarios) in a spec or the ADDED/MODIFIED part of a delta.

    A requirement's body is everything under its heading, scenarios included, so
    a changed scenario changes its requirement. A scenario's body is its own lines.
    """
    reqs = _blocks(text, delta)
    if mode == "requirement":
        return [Unit(h, _norm(body)) for h, body, _ in reqs]
    return [Unit(h, _norm(sb)) for _, _, scns in reqs for h, sb in scns]


def _blocks(text: str, delta: bool) -> list[tuple[str, list[str], list[tuple[str, list[str]]]]]:
    """(heading, every line under it, [(scenario heading, its lines)]) per requirement."""
    reqs: list[tuple[str, list[str], list[tuple[str, list[str]]]]] = []
    in_scope = False
    cur_req = cur_scn = None
    fence = None
    for line in text.splitlines():
        was_fenced = fence is not None
        fence = _fence_after(line, fence)
        if was_fenced or fence is not None:
            pass  # a fence line or a line inside one: content, never a heading
        else:
            m = _H2.match(line)
            if m:
                title = m.group(1).strip().upper()
                in_scope = title.startswith(("ADDED", "MODIFIED")) if delta else title.startswith("REQUIREMENTS")
                cur_req = cur_scn = None
                continue
            if in_scope:
                m = _REQ.match(line)
                if m:
                    cur_req = (_req_name(m.group(1)), [], [])
                    reqs.append(cur_req)
                    cur_scn = None
                    continue
                if _H3.match(line):
                    cur_req = cur_scn = None
                    continue
                m = _SCN.match(line)
                if m and cur_req is not None:
                    cur_scn = (_req_name(m.group(1)), [])
                    cur_req[2].append(cur_scn)
                    cur_req[1].append(line)
                    continue
                if _H4.match(line):
                    cur_scn = None
        if cur_req is not None:
            cur_req[1].append(line)
            if cur_scn is not None:
                cur_scn[1].append(line)
    return reqs


def _unclosed_fence(text: str) -> bool:
    """True when a code fence opens and the file ends before it closes (`_blocks` skips everything after it)."""
    fence = None
    for line in text.splitlines():
        fence = _fence_after(line, fence)
    return fence is not None


def _removed_headings(text: str) -> set[str]:
    out, in_removed = set(), False
    for line in text.splitlines():
        m = _H2.match(line)
        if m:
            in_removed = m.group(1).strip().upper().startswith("REMOVED")
        elif in_removed:
            r = _REQ.match(line)
            if r:
                out.add(_req_name(r.group(1)))
    return out


# OpenSpec's own line forms (its requirement-blocks parser): the bullet is optional and may be -, * or +.
_RENAME_LINE = re.compile(r"^\s*(?:[-*+]\s*)?(FROM|TO):\s*`?\s*###\s*Requirement:\s*(.+?)\s*`?\s*$")
_REMOVED_BULLET = re.compile(r"^\s*[-*+]\s*`?\s*###\s*Requirement:\s*(.+?)\s*`?\s*$")


def _delta_ops(text: str) -> tuple[set[str], dict[str, str], set[str]]:
    """(the requirements a delta's `## REMOVED` section removes, {old: new} from its `## RENAMED` section,
    the requirements its `## MODIFIED` section names).

    Lines inside a code fence are examples, not operations, so they are skipped."""
    removed: set[str] = set()
    renames: dict[str, str] = {}
    modified: set[str] = set()
    section, fence, pending = "", None, None
    for line in text.splitlines():
        was_fenced = fence is not None
        fence = _fence_after(line, fence)
        if was_fenced or fence is not None:
            continue
        m = _H2.match(line)
        if m:
            section, pending = m.group(1).strip().upper(), None
            continue
        if section.startswith("REMOVED"):
            r = _REQ.match(line) or _REMOVED_BULLET.match(line)
            if r:
                removed.add(_req_name(r.group(1)))
        elif section.startswith("RENAMED"):
            r = _RENAME_LINE.match(line)
            if r and r.group(1) == "FROM":
                pending = _req_name(r.group(2))
            elif r and pending is not None:
                renames[pending] = _req_name(r.group(2))
                pending = None
        elif section.startswith("MODIFIED"):
            r = _REQ.match(line)
            if r:
                modified.add(_req_name(r.group(1)))
    return removed, renames, modified


def _shared_scenarios(files: list["SpecFile"]) -> list[str]:
    """PROBLEM lines for a scenario heading one active delta would leave under two requirements of its spec.

    A proven scenario is keyed by (spec, heading), so one marker would prove every copy. Each active delta is
    read against the live spec alone, as archiving it would leave that spec: the live requirements minus the
    ones it REMOVES, renamed as it RENAMES them (their scenarios move with them), with its ADDED and MODIFIED
    blocks replacing the live copy. When one file holds every copy, that file's own `repeated` line reports
    it, so this adds none.

    Deliberately left unchecked, as before this check existed: (a) a clash between two active changes, and
    (b) a delta this reading cannot place safely, which is skipped whole: one that MODIFIES, RENAMES FROM or
    REMOVES a requirement the live spec (after the delta's own renames, for MODIFIED) does not hold, so it
    builds on another active change; and one whose RENAMED TO names a live requirement it does not itself
    remove or rename away, a collision OpenSpec rejects."""
    live = {f.spec: f for f in files if f.kind == "live"}
    problems: set[str] = set()
    for d in (f for f in files if f.kind == "active"):
        removed, renames, modified = _delta_ops(d.text)
        base = _blocks(live[d.spec].text, False) if d.spec in live else []
        names = {req for req, _, _ in base}
        projected = {renames.get(req, req) for req in names if req not in removed}
        if not (removed | set(renames)) <= names or not modified <= projected:
            continue  # builds on a requirement only another active change holds
        if any(new in names and new not in removed and new not in renames for new in renames.values()):
            continue  # renames onto a live requirement it keeps
        reqs: dict[str, tuple[list[str], str]] = {}  # requirement -> (its scenario headings, the file they come from)
        for req, _, scns in base:
            if req not in removed:
                reqs[renames.get(req, req)] = ([s for s, _ in scns], live[d.spec].rel)
        for req, _, scns in _blocks(d.text, True):
            reqs[req] = ([s for s, _ in scns], d.rel)
        held: dict[str, dict[str, set[str]]] = {}  # scenario -> requirement -> the files that put it there
        for req, (scns, rel) in reqs.items():
            for scn in scns:
                held.setdefault(scn, {}).setdefault(req, set()).add(rel)
        for scn, by_req in held.items():
            if len(by_req) < 2 or len({rel for rs in by_req.values() for rel in rs}) < 2:
                continue
            where = "; ".join(f"{req!r} in {', '.join(sorted(rs))}" for req, rs in sorted(by_req.items()))
            problems.add(
                f"PROBLEM repeated: {d.spec}: scenario {scn!r} sits under more than one requirement ({where}), "
                "so one marker would prove every copy; rename all but one"
            )
    return sorted(problems)


def _statement(body: list[str]) -> str:
    """A requirement's own sentence: its lines before the first `####` heading outside a fence."""
    out, fence = [], None
    for line in body:
        was_fenced = fence is not None
        fence = _fence_after(line, fence)
        if not was_fenced and fence is None and _H4.match(line):
            break
        out.append(line)
    return _norm(out)


def check_format(files: list["SpecFile"], limits: dict[str, int]) -> list[str]:
    """PROBLEM lines for each live spec or active delta over the limits. Archives are not edited, so skipped.

    A delta's requirement count is the size its spec would have after archiving: the live
    spec's requirements, plus the delta's new headings, minus the ones it removes."""
    problems = []
    live = {f.spec: f for f in files if f.kind == "live"}
    for f in files:
        if f.kind == "archived":
            continue
        reqs = _blocks(f.text, f.kind != "live")
        if "requirements" in limits:
            total = len(reqs)
            if f.kind == "active":
                base = {h for h, _, _ in _blocks(live[f.spec].text, False)} if f.spec in live else set()
                total = len(base | {h for h, _, _ in reqs}) - len(base & _removed_headings(f.text))
            if total > limits["requirements"]:
                problems.append(f"PROBLEM format: {f.rel}: {total} requirements, the limit is {limits['requirements']}")
        for heading, body, scns in reqs:
            if "scenarios" in limits and len(scns) > limits["scenarios"]:
                problems.append(
                    f"PROBLEM format: {f.rel}: requirement {heading!r} has {len(scns)} scenarios, the limit is {limits['scenarios']}"
                )
            if "chars" in limits:
                n = len(_statement(body))
                if n > limits["chars"]:
                    problems.append(f"PROBLEM format: {f.rel}: requirement {heading!r} states {n} characters, the limit is {limits['chars']}")
    return problems


def _opens_fence(m: re.Match[str] | None) -> bool:
    """True when `m`, a `_FENCE_LINE` match, opens a fence. A backtick run whose info string holds a backtick
    does not: the line is a code span (`` ```x``` ``), which is paragraph text."""
    return bool(m) and not (m.group(2)[0] == "`" and "`" in m.group(3))
