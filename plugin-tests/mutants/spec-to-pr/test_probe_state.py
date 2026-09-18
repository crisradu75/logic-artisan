"""Mutation batch for test_probe_state.py.

`probe_state.py` is resume detection: it decides what an interrupted run has
already done. Every failure here is expensive in the same direction — work that
WAS done reads as not done and gets redone, or work that was NOT done reads as
done and gets skipped. The second is worse, and mutants 1, 3, 6 and 7 are all
that shape.

**Mutants 2 and 3 look like one mutant and are not.** The round counter must be
BOTH deduped and a distinct-count rather than a max: a set-to-list refactor
survives max-semantics reasoning, and a max reimplementation survives
dedupe reasoning. Each is killed by exactly one test, which is why both are here.

**Mutant 7 is the dangerous-by-design one.** Turning `== 1` into `>= 1` makes an
ambiguous branch match stop refusing and adopt whichever branch `for-each-ref`
happened to list first — i.e. a run commits onto someone else's branch. Nothing
about the output shape changes.

**DELIBERATELY NOT MUTANTS:**

  * `_DATE_PREFIX`'s `^` anchor. `re.match` anchors at the start regardless, so
    the two patterns agree on every possible input — not a coverage gap but one
    rule written twice. CLAUDE.md's case for mutating the INPUT instead.
  * `return int(ahead.stdout.strip()) > 0` -> `>= 0`. No test has the feature
    branch exist while being zero commits ahead of base; every other path returns
    False earlier at `rev-parse`. A coverage gap, recorded below.
  * `if not owner_repo:` -> `if False:`. MACHINE-DEPENDENT, which is worse than
    unkillable. The mutant calls `gh pr view --repo ""`, which is not in the stub
    map, so the fake falls through to a REAL `subprocess.run`: on a machine with
    `gh` installed it exits non-zero and the test passes (survivor); without `gh`
    it raises and the test errors (kill). A verdict that depends on the
    developer's PATH is the intermittent survivor that trains readers to skip the
    list.

**Coverage gaps, recorded because a mutant cannot fix them:** `main()` is tested
by nothing — the usage message, the `return 2` on wrong arity, and the entire
stdout JSON contract the orchestrator parses are unexercised, since every test
reads `probe()`'s dict directly. `_implement_done`'s non-JSON branch, `_pr_state`'s
"no pull requests found" suppression, and `_resolved_branch_cache`'s caching are
all unreached too.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/spec-to-pr/test_probe_state.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

SCRIPT = PLUGIN / "skills" / "spec-to-pr" / "scripts" / "probe_state.py"

TARGETS = [DEV / "tests" / "skills" / "spec-to-pr" / "test_probe_state.py"]

MUTANTS = [
    (
        # Archived-change detection by suffix: change `bar` reads as archived
        # because a DIFFERENT archived change's dated directory happens to end
        # with `-bar`. The orchestrator then skips work nobody did.
        "the archive match goes back to a suffix match, so a change reads as "
        "already archived because another change's name ends with its name",
        SCRIPT,
        'if p.name[m.end():] == change_name and (p / "proposal.md").is_file():',
        'if p.name.endswith(change_name) and (p / "proposal.md").is_file():',
        TARGETS,
    ),
    (
        "the round counter stops deduping, so a round applied twice counts twice "
        "and Revise scopes its diff against a round that never happened",
        SCRIPT,
        "    rounds = {int(m.group(1)) for line in res.stdout.splitlines() for m in [pat.match(line)] if m}",
        "    rounds = [int(m.group(1)) for line in res.stdout.splitlines() for m in [pat.match(line)] if m]",
        TARGETS,
    ),
    (
        "the round count becomes max(N) again, so a squash that drops round 2 "
        "reports three rounds applied and the next round is skipped",
        SCRIPT,
        "    return len(rounds)",
        "    return max(rounds) if rounds else 0",
        TARGETS,
    ),
    (
        # A clone-time `origin/HEAD` cache left over from a master->main rename
        # names a ref that is gone; every `<base>..<branch>` range then dies as
        # `unknown revision`.
        "a dangling origin/HEAD is trusted unverified, so the base resolves to a "
        "branch that no longer exists and every commit range fails",
        SCRIPT,
        "        ).returncode == 0:",
        "        ).returncode >= 0:",
        TARGETS,
    ),
    (
        "a slash-containing default branch is truncated, so `origin/release/main` "
        "resolves to `main` — a branch that does not exist",
        SCRIPT,
        "        candidate = target[len(_ORIGIN_HEAD_PREFIX):] or None",
        '        candidate = target.rsplit("/", 1)[-1] or None',
        TARGETS,
    ),
    (
        "the branch fallback matches on a bare suffix, so `feature/hotfix-add-auth` "
        "answers for change `add-auth` and the probe reports on someone else's work",
        SCRIPT,
        '            if b and b.rsplit("/", 1)[-1] == change_name',
        "            if b and b.endswith(change_name)",
        TARGETS,
    ),
    (
        "an ambiguous branch match stops refusing and adopts the first one found, "
        "which is how a run commits onto the wrong branch",
        SCRIPT,
        "        if len(matches) == 1:",
        "        if len(matches) >= 1:",
        TARGETS,
    ),
    (
        "an unusable working directory is blamed on PATH again, so the reader is "
        "sent to look at the wrong thing",
        SCRIPT,
        "        if not cwd_is_dir:",
        "        if False:",
        TARGETS,
    ),
    (
        "a hung `gh` stops being survivable, so a credential prompt that runs to "
        "the timeout kills the probe and the orchestrator gets no JSON at all",
        SCRIPT,
        "    except (OSError, subprocess.SubprocessError) as exc:",
        "    except OSError as exc:",
        TARGETS,
    ),
]
