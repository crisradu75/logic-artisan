"""Mutant batch for `tests/hooks/test_block_worktree_path_escape.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_block_worktree_path_escape.py

The subject, `block-worktree-path-escape.py`, is a BLOCKING PreToolUse guard: inside
a linked git worktree it stops a Write/Edit whose target resolves outside the
current worktree (back into the primary clone, or into another linked worktree),
which is how one session's write can silently corrupt another session's checkout.
Each entry below re-breaks one real capability the hook depends on to make that
call correctly, chosen to be independently killable against the fixtures the
guard's own test file builds (a real `git worktree add` pair under `tmp_path`,
never a faked `.git` layout).

Two entries earn a longer note because the guard's own fixture shape determines
what they can prove. `worktree_pair` places the linked worktree as a SIBLING of
the primary clone under `tmp_path`, never nested inside it — so a target inside
the linked worktree is, mechanically, always caught by the "is this even inside
the primary clone at all" check (`_is_inside(target, primary_clone_root)`)
before the separate "is this inside MY worktree" check
(`_is_inside(target, worktree_root)`) is ever reached. That second check has no
killer in this suite as a result, and is deliberately not mutated here (see the
rejected mutant noted below). Mutants #4 and #7 target the two checks the
fixture DOES exercise, and between them cover the same two negative behaviours
the hook's docstring documents: a target outside the whole repo family must not
be blocked, and a legitimate relative-path write inside the worktree must not be
blocked either.

Paths resolve from this file's own location, matching every other batch in this
tree: a batch carrying an absolute developer path would leak a machine path into
synced core and only work on the machine that wrote it.

No anchor here spans a line break, so none of them need the CRLF-safe `_NL`
join `test_shipped_files_are_scanned.py` uses — every `old` below is verified
unique with `grep -c` against the raw file before being trusted here.

COUNT NOTE: 7 MUTANTS ARE NOT 7 INDEPENDENT PIECES OF EVIDENCE. Review measured
that mutants 2 (worktree detection) and 5 (in-worktree containment) have
IDENTICAL kill sets — the same three tests, and no assertion in the guard
distinguishes them. Both are kept because each re-breaks a real regression and a
reader looking for one would not find it under the other's name, but the honest
reading of a clean run is 6 distinct capabilities, not 7. Separating them needs a
test that reaches the second containment check with a target inside the primary
clone but outside worktree logic, which the sibling-worktree fixture shape
currently prevents.

PLATFORM NOTE, because a skip reads as a SURVIVED verdict. The inode-identity
mutant's only killer goes through `make_dir_alias`, which calls `pytest.skip`
when neither a symlink nor an NTFS junction can be created. On such a machine
the test skips, pytest exits 0, and that mutant reports SURVIVED with no
explanation -- a report about the machine, not about the batch.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                      # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "block-worktree-path-escape.py"
TARGETS = [DEV / "tests" / "hooks" / "test_block_worktree_path_escape.py"]

MUTANTS = [
    (
        # Escape-hatch env var. `ALLOW_WORKTREE_PATH_ESCAPE=1` is the
        # documented, deliberate override for a real exception; if the
        # comparison drifts off "1" the override silently stops working and a
        # session that believes it has opted out of the guard gets blocked
        # anyway. Killed by test_override_env_var_allows_a_deliberate_escape,
        # which sets the var to "1" and expects rc == 0.
        "the ALLOW_WORKTREE_PATH_ESCAPE override checks for the wrong value "
        "and a deliberate opt-out stops working",
        HOOK,
        'ALLOW_WORKTREE_PATH_ESCAPE") == "1"',
        'ALLOW_WORKTREE_PATH_ESCAPE") == "0"',
        TARGETS,
    ),
    (
        # Worktree detection itself: git reports the SAME absolute git-dir and
        # git-common-dir only for a primary clone (or a non-worktree repo) —
        # for a linked worktree the two diverge, because a worktree's `.git`
        # is a file pointing back at shared metadata rather than the
        # metadata itself. Flipping this equality makes the hook treat every
        # linked worktree as if it were the primary clone (skip all
        # protection) and vice versa. Killed by
        # test_blocks_an_escape_using_the_payload_cwd_not_the_process_cwd and
        # test_falls_back_to_the_process_cwd_when_the_payload_omits_it, both
        # of which need the guard to recognise a genuine linked worktree and
        # go on to block; with the comparison inverted it exits 0 immediately
        # instead.
        "the primary-clone-vs-linked-worktree equality is inverted, so a "
        "real linked worktree is treated as unprotected",
        HOOK,
        "if git_dir == git_common_dir:",
        "if git_dir != git_common_dir:",
        TARGETS,
    ),
    (
        # The containment test's fast path: normalise the case of both sides
        # and ask whether `root` is the common ancestor of `path` and `root`.
        # Feeding `root` in for BOTH arguments makes this comparison
        # trivially true no matter what `path` actually is, so `_is_inside`
        # answers "yes" for every path, including ones genuinely outside the
        # root. Killed directly by test_is_inside_still_says_no_for_a_genuinely_outside_path
        # and test_is_inside_rejects_a_sibling_whose_name_starts_with_the_root,
        # which call `_is_inside` and assert False for an outside path.
        "the containment test's commonpath check compares root against "
        "itself, so every path reads as contained",
        HOOK,
        "os.path.commonpath([os.path.normcase(path), os.path.normcase(root)]) == (",
        "os.path.commonpath([os.path.normcase(root), os.path.normcase(root)]) == (",
        TARGETS,
    ),
    (
        # The repo-family boundary: a target must be inside the primary
        # clone at all before the worktree-containment check even applies —
        # this is the branch that lets a target outside the whole repo
        # family (a memory dir, an unrelated clone) through untouched, per
        # the hook's own documented scope. Dropping the `not` inverts it:
        # now only a target ALREADY inside the primary clone returns early
        # (wrongly allowed — this defeats the escape block), while a target
        # genuinely outside the repo family falls through toward the block
        # message instead of being let through. Killed by
        # test_blocks_an_escape_using_the_payload_cwd_not_the_process_cwd
        # (rc becomes 0 instead of the expected 2) and by
        # test_a_target_outside_the_repo_family_is_allowed (rc becomes 2
        # instead of the expected 0) — one mutation, two independent kills.
        "dropping the negation on the repo-family check both allows the "
        "primary-clone escape and blocks a legitimate outside-repo write",
        HOOK,
        "if not _is_inside(target, primary_clone_root):",
        "if _is_inside(target, primary_clone_root):",
        TARGETS,
    ),
    (
        # The in-worktree containment check itself, checked against the
        # WRONG root: swapping `worktree_root` for `primary_clone_root` here
        # means "is this write inside my own worktree?" becomes "is this
        # write inside the primary clone?" — which every escape target
        # already satisfies (that is the point of the whole guard), so this
        # turns the check that is supposed to catch the escape into one that
        # always waves it through. Killed by
        # test_blocks_an_escape_using_the_payload_cwd_not_the_process_cwd and
        # test_falls_back_to_the_process_cwd_when_the_payload_omits_it, both
        # of which need this second check to say "no, not in my worktree"
        # for a target sitting in the primary clone.
        "the in-worktree containment check is compared against the primary "
        "clone root instead of the worktree root, so an escape target "
        "always passes it",
        HOOK,
        "if _is_inside(target, worktree_root):",
        "if _is_inside(target, primary_clone_root):",
        TARGETS,
    ),
    (
        # THE JUNCTION/SYMLINK TRAP the task calls out by name. `_is_inside`'s
        # fast path (normcase + commonpath) cannot see through a directory
        # alias — a junction on Windows, a symlink elsewhere — because the
        # alias is a textually different path to the same directory. That is
        # exactly why `_is_inside_by_inode` exists: it walks upward from the
        # target comparing `os.stat` results with `os.path.samestat`, which
        # answers "same directory?" by device+inode rather than by spelling.
        # Replacing that with a plain string comparison LOOKS equivalent —
        # both are just "is this ancestor the root?" — and every OTHER test
        # in the file stays green, because none of them alias a directory.
        # Only test_is_inside_survives_a_symlinked_spelling_on_every_platform
        # builds a real alias (via `make_dir_alias`, which falls back to an
        # NTFS junction on Windows, needing no elevated privileges) and
        # walks through an unresolved alias path — the one case a naive
        # string comparison cannot fold, since normcase alone (the fast
        # path, unaffected by this mutant) does not touch it either.
        "the inode-based directory-identity check (what lets this guard "
        "survive a junction/symlink alias) is replaced with plain string "
        "equality, which cannot see through the alias",
        HOOK,
        "if os.path.samestat(os.stat(current), root_stat):",
        "if current == root:",
        TARGETS,
    ),
    (
        # Relative `file_path` resolution. A relative target must resolve
        # against the SESSION's cwd (the payload cwd, read earlier into
        # `cwd`) — dropping the `os.path.join(cwd, file_path)` and using the
        # bare `file_path` instead means `os.path.realpath` resolves it
        # against this HOOK PROCESS's own cwd instead, exactly the
        # process-cwd-vs-payload-cwd bug this test file's docstring calls out
        # as the reason it exists. Killed by
        # test_a_relative_path_resolves_against_the_payload_cwd: writing
        # "seed.txt" from a worktree session (payload cwd = the worktree,
        # process cwd = the primary clone) is a legitimate in-worktree write
        # and must resolve to rc == 0; with the join dropped it resolves
        # against the process cwd instead, lands back in the primary clone,
        # and gets blocked (rc == 2).
        "a relative file_path resolves against the hook process's own cwd "
        "instead of the session's payload cwd, so a legitimate in-worktree "
        "relative-path write gets checked as if it targeted the primary "
        "clone and is blocked",
        HOOK,
        "file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)",
        "file_path if os.path.isabs(file_path) else file_path",
        TARGETS,
    ),
]
