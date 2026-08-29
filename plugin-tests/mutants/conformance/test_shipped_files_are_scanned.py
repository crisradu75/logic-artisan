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

THE MULTI-LINE ANCHOR IS BUILT OFF THE FILE, not spelled with a bare `\\n`.
Anchors are matched against raw bytes, and `.gitattributes` pins only the
launchers and the shell scripts — every `.py` here is subject to
`core.autocrlf=true`, which Git for Windows sets by default. A bare `\\n` matches
on the working copy that just WROTE the file and matches nothing the moment it is
checked out again, which is a preflight abort of the whole batch plus a red
`test_guards_have_mutant_batches.py` on a clone that changed nothing. `_NL` is
the fix `mutate.py`'s own preflight hint names.
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
GUARD = DEV / "tests" / "conformance" / "test_shipped_files_are_scanned.py"
PATH_GUARD = DEV / "tests" / "conformance" / "test_no_hardcoded_plugin_paths.py"
TARGETS = [DEV / "tests" / "conformance"]

_NL = "\r\n" if b"\r\n" in GUARD.read_bytes() else "\n"

GITATTRIBUTES_ENTRY = (
    '    ".gitattributes":' + _NL
    + '        "outside every scan root; carries line-ending rules, no prose or code",'
    + _NL
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
        '    "hooks/deleted-long-ago.sh": "stale",' + _NL + '    ".gitattributes":',
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
        "a token-scanner exemption stops naming the file it covers",
        GUARD,
        '    "skills/_shared/README.md":',
        '    "skills/_shared/READMEE.md":',
        TARGETS,
    ),
    (
        "the token split narrows back to a .md/.py whitelist, which is the hole "
        "review round 2 found: a .json the path scanner reaches but no token "
        "scanner does then satisfies neither map",
        GUARD,
        "    shipped = _shipped() - set(EXEMPT)",
        '    shipped = {n for n in _shipped() if n.endswith((".md", ".py"))}',
        TARGETS,
    ),
    (
        "the .json carrying _comment prose loses its token-scanner exemption",
        GUARD,
        '    "skills/_shared/references/required-permissions.json":',
        '    "skills/_shared/references/required-permissions-gone.json":',
        TARGETS,
    ),
    (
        "the source token scanner drops output-styles/*.md",
        PLUGIN / "skills" / "_shared" / "scripts" / "check_no_project_tokens.py",
        'md_roots = ("agents", "output-styles")',
        'md_roots = ("agents",)',
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
