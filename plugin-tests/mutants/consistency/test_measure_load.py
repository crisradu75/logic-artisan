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
        "a bare references/ path from a reference is not tried against its skill dir",
        SCRIPT,
        "            _skill_dir(source, root) / token,\n",
        "",
        GUARD,
    ),
    (
        "a bare sibling name is not tried beside the naming file",
        SCRIPT,
        "            source.parent / token,\n",
        "",
        GUARD,
    ),
    (
        "a ../ path escaping the plugin is followed",
        SCRIPT,
        "        if not candidate.is_relative_to(root):",
        "        if False:",
        GUARD,
    ),
    (
        "references trusts its caller to have resolved the root",
        SCRIPT,
        "    root, source = root.resolve(), source.resolve()",
        "    root, source = root, source.resolve()",
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
        "only a bare `true` disables model invocation",
        SCRIPT,
        '    return value.split("#")[0].strip().strip("\\"\'").lower() in _YAML_TRUE',
        '    return value.strip() == "true"',
        GUARD,
    ),
    (
        "an opt-in output style is counted as paid every session",
        SCRIPT,
        '        if not _is_true(_frontmatter(style).get("force-for-plugin", "")):',
        "        if False:",
        GUARD,
    ),
    (
        "descriptions are keyed by name, so a collision overwrites one",
        SCRIPT,
        "        descriptions[path.relative_to(root).as_posix()] = len(",
        '        descriptions[_frontmatter(path).get("name", path.parent.name)] = len(',
        GUARD,
    ),
    (
        "a profile entry passes when merely reachable, not named by its forcing file",
        SCRIPT,
        "            elif path.resolve() not in references(root / forced_by, root):",
        "            elif path.resolve() not in reachable(root / forced_by, root):",
        GUARD,
    ),
    (
        "a forcing file outside the profile is accepted",
        SCRIPT,
        "            elif forced_by not in files:",
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
    (
        "an unknown --skill exits 0",
        SCRIPT,
        "            print(f\"no such skill: {args.skill}\", file=sys.stderr)\n            return 2",
        "            print(f\"no such skill: {args.skill}\", file=sys.stderr)\n            return 0",
        GUARD,
    ),
    (
        "--skill lists references smallest first",
        SCRIPT,
        "key=lambda kv: -kv[1]",
        "key=lambda kv: kv[1]",
        GUARD,
    ),
]
