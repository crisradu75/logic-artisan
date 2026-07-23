"""Discover open OpenSpec changes and propose an implementation sequence.

Lists every non-archived directory under openspec/changes/ that has at
least one of proposal.md/design.md/tasks.md (a directory with none of the
three isn't a real change yet and is skipped). For each discovered change,
reads those same files for lines that mention another discovered change's
name as a whole kebab-case token (not merely a substring — "add-foo" does
NOT match inside "add-foo-extended") appearing AFTER a dependency-signal
word ("depends"/"depend", "prerequisite", "requires"/"require", "after",
"merged first", "needs"/"need") within a short character window on the
same line — direction matters: a name preceding every signal word on the
line does NOT count, since this repo's real dependency prose is
consistently "Depends on X (...) being merged" (object follows the verb),
and a name appearing only before the signal word is typically the opposite
direction (e.g. a change's own "before X or Y depend on them", referring
back to itself). Every signal-word occurrence on a line gets its own
window. Topologically sorts the result via Kahn's algorithm (stable
tie-break: original discovery order).

This is a BEST-EFFORT heuristic, not an authority — it will miss an
implicit dependency stated without a signal word or one whose name falls
outside the window, and it can still false-positive on a sentence that
happens to combine a signal word with an unrelated change name within the
window (e.g. "unlike add-foo, this ships independently").
The orchestrator (multi-pr) MUST sanity-check the proposed order by reading
each change's own "Why"/"Depends on" prose before trusting it, and must ask
the user rather than guess when `cycle_detected` is true or a dependency
looks ambiguous.

Cycle handling distinguishes two kinds of "couldn't be ordered" node:
`cycle_members` are nodes that literally sit on a directed cycle (A depends
on B depends on A); `blocked_by_cycle` are nodes that aren't themselves
cyclic but depend, directly or transitively, on a node that is — Kahn's
algorithm can't order either kind, but only the first kind is an actual
cycle the user needs to resolve.

Output: single JSON object on stdout (success path, exit 0).
{
  "changes": [
    {"name": "...", "prerequisites": ["..."], "has_proposal": true}
  ],
  "order": ["...", "..."],
  "cycle_detected": false,
  "cycle_members": [],
  "blocked_by_cycle": []
}

On the one error path (openspec/ itself doesn't exist -- not an
OpenSpec-enabled repo), stdout is a single-key object instead:
{"error": "openspec/ not found under <path>"}, and the process exits 1.
Exit 0 covers every other case, including zero changes found (a valid
state, not an error).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_DEPENDENCY_CONTEXT = re.compile(
    r"\b(depends?|prerequisite|requires?|after|merged first|needs?)\b",
    re.IGNORECASE,
)

_ARTIFACT_FILES = ("proposal.md", "design.md", "tasks.md")


def _discover_change_names(changes_dir: Path) -> list[str]:
    if not changes_dir.is_dir():
        return []
    names = []
    for p in sorted(changes_dir.iterdir()):
        if not p.is_dir() or p.name == "archive":
            continue
        if any((p / f).is_file() for f in _ARTIFACT_FILES):
            names.append(p.name)
    return names


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _name_appears_as_token(name: str, line: str) -> bool:
    """True iff `name` appears in `line` as a whole kebab-case token --
    i.e. not immediately preceded or followed by another `[a-z0-9-]`
    character. Plain substring matching would let "add-foo" match inside
    "add-foo-extended"; this doesn't."""
    pattern = re.compile(r"(?<![a-z0-9-])" + re.escape(name) + r"(?![a-z0-9-])", re.IGNORECASE)
    return pattern.search(line) is not None


_MAX_DEPENDENCY_WINDOW = 120  # chars after a signal word within which a name must appear to count


def _find_prerequisites(change_dir: Path, other_names: list[str], self_name: str) -> list[str]:
    prereqs: set[str] = set()
    for filename in _ARTIFACT_FILES:
        text = _read_text(change_dir / filename)
        if not text:
            continue
        for line in text.splitlines():
            # Every signal-word occurrence on the line gets its own window,
            # not just the first (`finditer`, not `search`) -- a line with
            # an early, incidental signal word (e.g. "after", a common
            # English word) followed much later by the REAL "requires X
            # merged" clause would otherwise put X outside the first
            # match's window and silently miss a genuine prerequisite.
            # Confirmed regression: "Delivered after <130 chars of prose>
            # ... it requires add-real merged." only detects add-real when
            # every signal match's own window is checked, not just the
            # line's first one.
            for signal_match in _DEPENDENCY_CONTEXT.finditer(line):
                # Only a name that appears AFTER a signal word, within a
                # short window, counts as a real prerequisite reference.
                # This repo's actual dependency phrasing is consistently
                # "Depends on X (...) being merged" / "requires X merged" --
                # the prerequisite name follows the verb. A name appearing
                # BEFORE every signal word on the line (e.g. "...before the
                # ETL (X) or the page (Y) depend on them", where "them"
                # refers back to THIS change) is the opposite direction and
                # must not be read as "this change depends on X/Y".
                # Confirmed false positive this fixes:
                # add-operator-delivery-data-plane's own proposal has
                # exactly this shape and was wrongly flagged as depending on
                # both of its downstream consumers
                # (add-operator-as-run-import,
                # add-operator-evaluation-stage), producing a spurious
                # 3-node dependency cycle across changes that were actually
                # a clean linear chain.
                window = line[signal_match.end():signal_match.end() + _MAX_DEPENDENCY_WINDOW]
                for other in other_names:
                    if other == self_name:
                        continue
                    if _name_appears_as_token(other, window):
                        prereqs.add(other)
    return sorted(prereqs)


def _kahn_order(by_name: dict[str, dict], discovery_index: dict[str, int]) -> tuple[list[str], list[str]]:
    """Kahn's algorithm with a stable tie-break (original discovery order).
    Returns (order, remaining) -- `remaining` is every node Kahn's couldn't
    place, which conflates true cycle members with nodes merely downstream
    of one. Callers that need to tell those apart should follow up with
    `_cycle_members`."""
    in_degree = {name: 0 for name in by_name}
    dependents: dict[str, list[str]] = {name: [] for name in by_name}
    for name, c in by_name.items():
        for prereq in c["prerequisites"]:
            if prereq not in by_name:
                continue  # dependency outside the discovered set (already merged, or unresolved reference) -- ignore
            in_degree[name] += 1
            dependents[prereq].append(name)

    queue = sorted((name for name in by_name if in_degree[name] == 0), key=discovery_index.get)
    order: list[str] = []
    while queue:
        name = queue.pop(0)
        order.append(name)
        newly_ready = []
        for dependent in dependents[name]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                newly_ready.append(dependent)
        queue.extend(newly_ready)
        queue.sort(key=discovery_index.get)

    remaining = [name for name in by_name if name not in order]
    return order, remaining


def _cycle_members(by_name: dict[str, dict]) -> list[str]:
    """Nodes that participate in an actual directed cycle (can reach
    themselves via prerequisite edges) -- as opposed to merely being
    downstream of one, which Kahn's algorithm alone can't distinguish (a
    node with a single cyclic prerequisite never reaches in-degree 0
    either, even though it isn't itself part of the cycle). Plain
    DFS with white/gray/black coloring; fine for the small graphs this
    heuristic deals with (a handful of concurrently open OpenSpec changes,
    not thousands)."""
    graph = {name: [p for p in c["prerequisites"] if p in by_name] for name, c in by_name.items()}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in graph}
    in_cycle: set[str] = set()

    def visit(node: str, stack: list[str]) -> None:
        color[node] = GRAY
        stack.append(node)
        for prereq in graph[node]:
            if color[prereq] == GRAY:
                # Back-edge: everything on the stack from prereq's position
                # onward forms a cycle.
                idx = stack.index(prereq)
                in_cycle.update(stack[idx:])
            elif color[prereq] == WHITE:
                visit(prereq, stack)
        stack.pop()
        color[node] = BLACK

    for name in graph:
        if color[name] == WHITE:
            visit(name, [])
    return sorted(in_cycle)


def discover(changes_dir: Path) -> dict:
    names = _discover_change_names(changes_dir)
    changes = []
    for name in names:
        change_dir = changes_dir / name
        prereqs = _find_prerequisites(change_dir, names, name)
        changes.append({
            "name": name,
            "prerequisites": prereqs,
            "has_proposal": (change_dir / "proposal.md").is_file(),
        })

    by_name = {c["name"]: c for c in changes}
    discovery_index = {name: i for i, name in enumerate(by_name)}
    order, remaining = _kahn_order(by_name, discovery_index)
    cycle_members = _cycle_members(by_name) if remaining else []
    blocked_by_cycle = sorted(set(remaining) - set(cycle_members))

    return {
        "changes": changes,
        "order": order,
        "cycle_detected": bool(cycle_members),
        "cycle_members": cycle_members,
        "blocked_by_cycle": blocked_by_cycle,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repo root (defaults to cwd).")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    openspec_dir = repo_root / "openspec"
    if not openspec_dir.is_dir():
        print(json.dumps({"error": f"openspec/ not found under {repo_root}"}))
        print(f"discover_sequence: no openspec/ directory at {repo_root}", file=sys.stderr)
        return 1

    result = discover(openspec_dir / "changes")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
