"""Mutant batch for `tests/conformance/test_shipped_files_are_scanned.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/conformance/test_shipped_files_are_scanned.py

The guard's claim is that a shipped file falling outside every scanner is
reported rather than absorbed. On a correct tree that branch never executes, so
each entry below re-creates one of the ways coverage has actually been lost or
mis-recorded: a scanner narrowed, an exemption list that stopped matching the
tree, and the two staleness directions.

Two entries mutate the guard's INPUTS rather than the guard — the `EXEMPT` data
and another scanner's suffix tuple. That is deliberate: where a rule and its
data agree on every correct input, the data is what discriminates. Mutating
`test_every_exemption_carries_a_reason`'s own comprehension to `[]`, for
instance, is unkillable, because `assert not []` is exactly what a clean run
asserts.

Paths resolve from this file's own location: a batch with an absolute developer
path works on one machine and leaks a repo name into synced core.
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
GUARD = DEV / "tests" / "conformance" / "test_shipped_files_are_scanned.py"
PATH_GUARD = DEV / "tests" / "conformance" / "test_no_hardcoded_plugin_paths.py"
TARGETS = [DEV / "tests" / "conformance"]

GITATTRIBUTES_ENTRY = (
    '    ".gitattributes":\n'
    '        "outside every scan root; carries line-ending rules, no prose or code",\n'
)

MUTANTS = [
    (
        "an unscanned shipped file loses its exemption and nothing reports it",
        GUARD,
        GITATTRIBUTES_ENTRY,
        "",
        TARGETS,
    ),
    (
        "an exemption is kept but its stated reason is emptied",
        GUARD,
        '"outside every scan root; carries line-ending rules, no prose or code",',
        '"",',
        TARGETS,
    ),
    (
        "an exemption outlives the file it names",
        GUARD,
        '    ".gitattributes":',
        '    "hooks/deleted-long-ago.sh": "stale",\n    ".gitattributes":',
        TARGETS,
    ),
    (
        "the path scanner drops .json, stranding hooks/hooks.json unscanned",
        PATH_GUARD,
        'SCANNED_SUFFIXES = (".md", ".py", ".mjs", ".json")',
        'SCANNED_SUFFIXES = (".md", ".py", ".mjs")',
        TARGETS,
    ),
    (
        "the path scanner drops the hooks/ root entirely",
        PATH_GUARD,
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "hooks", "lib")',
        'SCANNED_ROOTS = ("skills", "agents", "output-styles", "lib")',
        TARGETS,
    ),
    (
        "the shipped-file enumeration narrows to one subdirectory",
        GUARD,
        '["git", "ls-files", "-z", "--", _PUBLISHED_PREFIX]',
        '["git", "ls-files", "-z", "--", _PUBLISHED_PREFIX + "/agents"]',
        TARGETS,
    ),
    (
        "the dead-exemption branch stops reporting",
        GUARD,
        "vanished = sorted(name for name in exempt if name not in shipped)",
        "vanished = []",
        TARGETS,
    ),
    (
        "the now-covered branch stops reporting",
        GUARD,
        "now_covered = sorted(name for name in exempt if name in shipped & reached)",
        "now_covered = []",
        TARGETS,
    ),
]
