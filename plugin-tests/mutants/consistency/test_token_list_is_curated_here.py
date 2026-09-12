"""Mutation batch for test_token_list_is_curated_here.py.

The guard claims that the conformance checker cannot be SILENTLY DISABLED in this
repo. `check_no_project_tokens.py` treats an absent `project-tokens.local.md` as a
trivial pass — correct in a consuming repo, a hole in the source repo, where a
path typo or a move turns the whole token scan off with a green suite and no
signal.

**Every mutant targets the SHIPPED SCRIPT, not the guard.** That is the point of
this pairing: the guard's own docstring records that a version computing its own
repo root "passed happily while the guard's anchor was off by one level and the
guard skipped". So the thing to break is the resolution the guard borrows —
`TOKEN_LIST_RELPATH`, `_repo_root()`, `load_tokens()` — and the question each
mutant asks is whether this guard notices its subject going blind.

**Both assertions are covered, deliberately.** Mutants 1-2 break the PATH, so
`token_path.is_file()` goes false and the first assertion fires. Mutants 3-4 leave
the path correct and break the PARSE, so the file is found but yields zero tokens
and only the second assertion fires — the one guarding against "the guard runs
against an empty list, which passes everything". A batch hitting only the first
would leave the emptiness check unproven.

**A note on blast radius.** These mutants edit a script the conformance scope also
exercises, so a wider target would be killed by tests that are not this guard. The
target is pinned to this one guard file precisely so a kill means THIS guard
noticed — `mutate.py`'s docstring asks for the narrowest target that could
plausibly catch the mutation, and here narrow is also what makes the verdict mean
anything.

**ONE MUTANT WAS WRITTEN, RUN, AND DELETED — the reason is the point.** Disabling
`_repo_root()`'s git branch (`if out.returncode == 0 and out.stdout.strip():` ->
`if False:`) SURVIVES, and it could not do otherwise. The fallback walks parents
for the first non-global `.claude`, and in this repo that lands on the same
directory git reports — measured from the checker's own location:

    branch A (git rev-parse) : <repo root>
    branch B (.claude walk)  : <repo root>       resolve() equal: True

Both then resolve the token list to the same existing file, so no input this repo
can present distinguishes the two. That is CLAUDE.md's "two rules agree on all
correct inputs", and the rule is to mutate the input rather than the guard — but
the discriminating input is a marketplace install, where the walk finds the user's
GLOBAL `~/.claude` and the git call is what saves it. That environment cannot be
built inside this batch. Deleted rather than shipped as a permanent survivor,
because a survivor nobody can act on trains the next reader to skip the list.
Upstream issue #52 is the record that the fallback really does fail there.

Anchors are single-line: the script is CRLF, where a bare `\\n` matches nothing.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_token_list_is_curated_here.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

CHECKER = PLUGIN / "skills" / "_shared" / "scripts" / "check_no_project_tokens.py"
GUARD = DEV / "tests" / "consistency" / "test_token_list_is_curated_here.py"
TARGET = [GUARD]

MUTANTS = [
    # ---- 1-3: the path goes wrong, so the list is never found ----
    (
        "TOKEN_LIST_RELPATH points at the pre-move location — the exact class of "
        "break this guard exists for, since the list already travelled once from "
        "a skill's references/ to cla.io/",
        CHECKER,
        'TOKEN_LIST_RELPATH = Path("cla.io") / "project-tokens.local.md"',
        'TOKEN_LIST_RELPATH = Path("references") / "project-tokens.local.md"',
        TARGET,
    ),
    (
        "a filename typo in the relpath — the list resolves nowhere and every "
        "token scan becomes a trivial pass",
        CHECKER,
        'TOKEN_LIST_RELPATH = Path("cla.io") / "project-tokens.local.md"',
        'TOKEN_LIST_RELPATH = Path("cla.io") / "project-tokens.local.markdown"',
        TARGET,
    ),
    # ---- 3-4: the path is right, the PARSE yields nothing ----
    (
        "load_tokens stops recognising `- ` bullets, so a correctly-located list "
        "parses to zero tokens and the scan passes everything",
        CHECKER,
        '        if line.startswith("- ") or line.startswith("* "):',
        '        if line.startswith("+ "):',
        TARGET,
    ),
    (
        "load_tokens collects nothing at all — the file is found, is non-empty, "
        "and still yields an empty list",
        CHECKER,
        "                tokens.append(body)",
        "                pass",
        TARGET,
    ),
]
