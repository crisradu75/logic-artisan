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
# Derived from the file it is inserted INTO, not from the guard. `.gitattributes`
# and the `.py` files happen to share a line ending on both platforms today, but
# borrowing one file's separator for an edit to another is the kind of coupling
# that holds until it silently does not — and a wrong separator here aborts the
# whole batch at preflight.
_ATTR = PLUGIN / ".gitattributes"
_NL_ATTR = "\r\n" if b"\r\n" in _ATTR.read_bytes() else "\n"

# The planted path, ASSEMBLED rather than spelled, and both halves of that are
# forced.
#
# `test_no_batch_hardcodes_an_absolute_path` runs the shipped checker's own
# regexes over every line of every batch, so spelling a Windows drive path here
# fails the suite — correctly: a batch carrying an absolute developer path works
# on one machine. It caught the first version of this entry, and then caught the
# second, where the only offender left was THIS COMMENT explaining the first.
# That guard honours `path-fixture-ok` and nothing else: unlike the shipped
# checker it does NOT exempt a placeholder-looking path, so prose here cannot
# name the shape even to say it is forbidden. Describe it in words.
#
# The declared escape hatch, `path-fixture-ok`, is NOT usable here and that is
# the interesting part. The marker exempts the LINE it appears on, and the line
# this literal sits on is the mutant's replacement text — so the marker would
# travel into the file being mutated, where the guard under test skips marked
# lines too. The mutant would then plant a path nothing reports and SURVIVE,
# which is a false negative wearing a real finding's costume. Splitting the
# string keeps every source line here below both regexes while the assembled
# value is a genuine path with no marker on it.
_BACKSLASH = chr(92)
_PLANTED_PATH = "C:" + _BACKSLASH.join(["", "Users", "someone", "proj"])

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
        # Description corrected: `hooks/hooks.json` is no longer STRANDED by
        # this edit. Issue #190 widened the token scanner to `.json`, so all
        # three `.json` files keep a reader and the coverage guard stays green.
        # What now fires is the count floor alone — 103 - 3 = 100 against `>= 102`
        # — plus the `REQUIRED_SUFFIXES` assertion. The old wording described
        # the pre-#190 tree and would have sent a reader looking for a coverage
        # failure that no longer happens.
        "the path scanner drops .json; the count floor is what catches it",
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
        # Replaces "the .json carrying _comment prose loses its token-scanner
        # exemption", whose anchor was that file's TOKEN_EXEMPT line — deleted by
        # issue #190 when the token scanner grew a `.json` scan and the exemption
        # stopped being true. It was in any case the same assertion as "an
        # exemption outlives the file it names" above, on a different entry.
        #
        # This is the mutant the widening earns: revert the suffix and the three
        # shipped `.json` files fall outside every token scanner with nothing in
        # TOKEN_EXEMPT to explain them, which is the `unexplained` branch.
        "the source token scanner drops .json, stranding the two "
        "required-permissions files and hooks/hooks.json unscanned",
        PLUGIN / "skills" / "_shared" / "scripts" / "check_no_project_tokens.py",
        # Anchored on the tuple alone, not the whole `if` line. The line is
        # wrapped, so including ` or (` bakes the current formatting into the
        # anchor and a reflow or a fifth suffix breaks it — loudly, at
        # preflight, but for no reason. (The anchor moved once already, when
        # issue #254 made the tuple three-long; that is the preflight working.)
        '(".py", ".json", ".sh")',
        '(".py", ".sh")',
        TARGETS,
    ),
    (
        # The mutant issue #254's widening earns, and the mirror of the one
        # above. Revert `.sh` and `hooks/probe-python.sh` has no reader at all:
        # the path scanner does not take `.sh` either, and the file left `EXEMPT`
        # in that same change precisely because a scanner had grown to reach it.
        # So it lands in `unexplained` in BOTH coverage guards — which is what
        # makes the widening load-bearing rather than decorative, and what stops
        # the wiring rationale now living in that file from sitting unscanned.
        "the source token scanner drops .sh, leaving hooks/probe-python.sh — the "
        "declared home of the hooks.json wiring rationale — with no reader",
        PLUGIN / "skills" / "_shared" / "scripts" / "check_no_project_tokens.py",
        '(".py", ".json", ".sh")',
        '(".py", ".json")',
        TARGETS,
    ),
    (
        # Re-breaks a real regression: `mechanical-checks.mjs` loses its only
        # reader. TWO guards fail on it, and the claim that only one does was
        # wrong — recorded here because the wrong version shipped first and two
        # reviewers measured it independently.
        #
        #   * `test_the_scan_is_not_vacuous`'s `REQUIRED_SUFFIXES` assertion,
        #     with `missing == ['.mjs']`. The count floor does NOT fire: `.mjs`
        #     is one file against a margin of one, so 103 -> 102 lands exactly ON
        #     `>= 102` and clears it.
        #   * `test_every_shipped_file_is_scanned_or_deliberately_exempt`, because
        #     `mechanical-checks.mjs` sits in `TOKEN_EXEMPT` and NOT in `EXEMPT`
        #     — the path scanner is its only reader, so dropping the suffix puts
        #     it in `unexplained`.
        #
        # So this mutant does not, on its own, prove the suffix assertion can
        # fire: revert `REQUIRED_SUFFIXES` to `set(SCANNED_SUFFIXES)` — back to
        # the tautology the assertion exists to replace — and it still dies, on
        # the coverage guard. NO single-edit mutant can isolate that assertion
        # today. Isolating it needs a suffix with exactly one file that some
        # OTHER scanner also reaches, so the floor and the coverage guard both
        # stay green; `.mjs` is one file but path-scanner-only, and `.json` is
        # three files. Neither qualifies, and inventing a file to make one
        # qualify would be fixture-shaped evidence about nothing.
        #
        # The assertion's own firing is therefore established by a read-only
        # patch instead, cited at its definition in the guard. That is the
        # honest split: this batch proves the regression is caught, and the
        # patch proves which assertion catches it. Claiming exclusivity from a
        # batch that reports only killed/survived over a whole directory is
        # CLAUDE.md check 3 — reasoning shipped with a measurement's authority.
        "the path scanner drops .mjs, stranding mechanical-checks.mjs with no "
        "reader; the count floor cannot see it, two other guards can",
        PATH_GUARD,
        'SCANNED_SUFFIXES = (".md", ".py", ".mjs", ".json")',
        'SCANNED_SUFFIXES = (".md", ".py", ".json")',
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
        # The review finding that the exempt files' cleanliness was recorded by a
        # grep which could not match a real path. The claim is now executed, so it
        # is mutable: plant the shape in an EXEMPT file and the guard must say so.
        # `.gitattributes` is the carrier because it is the one exempt file whose
        # content is pure configuration — no prose that could legitimately quote a
        # path — and it is already this batch's anchor file for the same reason.
        "an exempt file, which NO scanner opens, acquires a hardcoded absolute "
        "developer path",
        _ATTR,
        "hooks/*.sh      text eol=lf",
        f"# see {_PLANTED_PATH} for why"
        + _NL_ATTR
        + "hooks/*.sh      text eol=lf",
        TARGETS,
    ),
    (
        # The positive control's own mutant. Without it the absence assertion above
        # reports clean for a detector that matches nothing — which is precisely
        # how the grep version passed while proving nothing, twice.
        "the developer-path detector stops detecting, so the exempt-file check "
        "passes vacuously the way its grep predecessor did",
        GUARD,
        "    win = _TOKENS.WIN_ABS_PATH.search(text)",
        "    win = None",
        TARGETS,
    ),
    (
        # The THIRD shape, which the first version of `_developer_path_kinds`
        # omitted entirely — it implemented two of the shipped checker's three
        # kinds and called itself a copy of them. Review found it; nothing here
        # could have, because the control only exercised the two that existed.
        # One mutant per kind now, so dropping any one of them fails.
        "the separator-stripped shape stops being detected — the kind the "
        "checker's own comment says a real developer username survived on",
        GUARD,
        "    mangled = _TOKENS.MANGLED_WIN_PATH.search(text)",
        "    mangled = None",
        TARGETS,
    ),
    (
        "the home-directory shape stops being detected",
        GUARD,
        "    home = _TOKENS.HOME_ABS_PATH.search(text)",
        "    home = None",
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
