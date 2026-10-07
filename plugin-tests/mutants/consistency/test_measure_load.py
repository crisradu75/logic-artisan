"""Mutation batch for test_measure_load.py.

Each mutant breaks one rule the meter's numbers depend on. A meter that
silently drops a reference, follows one into another skill, or counts an
unlisted description still prints a plausible table, and a before/after
quoted from it is wrong by exactly the amount nobody checks.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_measure_load.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]

SCRIPT = DEV / "scripts" / "measure_load.py"

# Scoped to the ONE guard file, so a kill is evidence about this guard.
GUARD = [DEV / "tests" / "consistency" / "test_measure_load.py"]

MUTANTS = [
    (
        "reachable follows any .md, so another skill's SKILL.md and its references count",
        SCRIPT,
        '        if target is None or target.parent.name != "references":',
        "        if target is None:",
        GUARD,
    ),
    (
        "a bare references/ path resolves against the plugin root, not the naming skill",
        SCRIPT,
        '        candidates = [_skill_dir(source, root) / token, root / "skills" / token, root / token]',
        '        candidates = [root / "skills" / token, root / token]',
        GUARD,
    ),
    (
        "a ../ path escaping the plugin is followed",
        SCRIPT,
        "        if not candidate.is_relative_to(resolved_root):",
        "        if False:",
        GUARD,
    ),
    (
        "reachable stops at depth one",
        SCRIPT,
        "                queue.append(target)",
        "                pass",
        GUARD,
    ),
    (
        "a disable-model-invocation skill's description is counted in the session",
        SCRIPT,
        '        if fields.get("disable-model-invocation", "").lower() == "true":',
        "        if False:",
        GUARD,
    ),
    (
        "an indented key overrides the top-level one",
        SCRIPT,
        '        if line[:1] in (" ", "\\t", "#") or ":" not in line:',
        '        if ":" not in line:',
        GUARD,
    ),
    (
        "check_profiles accepts a file its skill no longer reaches",
        SCRIPT,
        "            elif path.resolve() not in refs:",
        "            elif False:",
        GUARD,
    ),
    (
        "a stale profile still exits 0",
        SCRIPT,
        "            print(f\"stale profile: {problem}\", file=sys.stderr)\n        return 2",
        "            print(f\"stale profile: {problem}\", file=sys.stderr)\n        return 0",
        GUARD,
    ),
]
