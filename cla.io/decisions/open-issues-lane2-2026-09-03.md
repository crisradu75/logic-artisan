# Decision: the three commit-provenance issues, one PR each

Built 2026-09-03 from `gh issue list --state open` (9 issues) on `main` at `98e4d37`, after the
lane-1 batch closed (#193, #180, #177).

Three of the nine open issues — **#198, #199, #200** — all concern the commit-provenance hook and
its test, and all three are decidable from the issue text plus one reproduction. They are this
document. The other six are listed under "Out of scope"; four of those are unchanged from
`open-issues-lane1-2026-09-02.md` and are not re-argued here.

**Measured-by** (all run 2026-09-03 from the repo root, on `98e4d37`):

```
gh issue list --state open --limit 100                                    → 9

grep -rn '"python"' plugin-tests/tests/hooks/test_log_commit_provenance.py
      → :137, :191 — the two call sites, and the only ones
grep -rln 'sys.executable' plugin-tests/tests
      → 13 test files already use it, so it is the house convention, not a new idea

grep -n 'PreToolUse\|PostToolUse' .claude/plugins/cla/hooks/hooks.json
      → :42 PreToolUse, :74 PostToolUse; log-commit-provenance is wired at :86-:90 on PostToolUse only

grep -rn 'Measured-by' .claude/plugins/cla/ --include=*.md
      → 5 instruction sites in 4 files: lite-pr/SKILL.md:122,:125,:135;
        spec-to-pr/SKILL.md:119,:121,:345; spec-to-pr/references/ship.md:48,:51,:55,:68,:71;
        spec-to-pr/references/revise.md:208
      → none of the five shows Co-Authored-By at all, so none states where it goes

wc -l < cla.io/retro/commit-provenance.jsonl                              → 145
measured_by_count distribution over that file
      → {0:121, 2:2, 3:6, 4:2, 5:1, 6:8, 7:3, 8:1, 9:1} — 121 zeros, 24 non-zero
```

**Reproductions run in a scratch repo on 2026-09-03**, both quoted in the candidates below:

```
# the trailer blank line (#200)
git commit -m "s" -m "Measured-by: a — b\nMeasured-by: c — d" -m "Co-Authored-By: X <x@y>"
  then git log -1 --pretty='%(trailers:key=Measured-by,valueonly=true,unfold=true)' → 0 values
same message with Co-Authored-By inside the second -m                               → 2 values

# the reflog signal (#199)
after a real commit          git reflog -1 --format='%gs' → "commit (initial): first"
after a commit with nothing staged (exit 1)               → "commit (initial): first"  (unchanged)
after git checkout -b other                               → "checkout: moving from master to other"
```

## Sequencing

**One dependency edge.** A and B both edit
`plugin-tests/tests/hooks/test_log_commit_provenance.py`, so **A must merge before B runs**.
C touches only skill markdown and is independent — leave its PR open.

| item | issue | files it edits | merge? |
|---|---|---|---|
| A | #198 | `plugin-tests/tests/hooks/test_log_commit_provenance.py` | **merge before B** |
| B | #199 | `.claude/plugins/cla/hooks/log-commit-provenance.py`, the same test file | leave open |
| C | #200 | `lite-pr/SKILL.md`, `spec-to-pr/SKILL.md`, `spec-to-pr/references/ship.md`, `spec-to-pr/references/revise.md` | leave open |

Run order A → B → C.

---

## A — #198: the test hardcodes `python`

**Decided.** Replace the bare interpreter name with `sys.executable` at both call sites.

**What to do.** `plugin-tests/tests/hooks/test_log_commit_provenance.py:137` and `:191` both spell
`["python", str(_HOOK)]`. Use `[sys.executable, str(_HOOK)]`, adding the `sys` import if absent.

**Why this spelling and not `python3`.** 13 other test files under `plugin-tests/tests/` already use
`sys.executable`, which is correct on every platform and needs no alias to exist. Hardcoding
`python3` instead would swap one machine-dependent name for another.

**Not verifiable on a Windows dev machine, and that is expected.** The 9 failures reproduce only
where `python3` exists and `python` does not. Locally the suite is green either way, so a green run
is evidence the fix did not break anything — not evidence it fixed anything. Do not write a
`Measured-by:` trailer claiming otherwise.

**Out of scope.** Do not touch the hook. `hooks/log-commit-provenance.py` carries
`#!/usr/bin/env python3` and is invoked through `probe-python.sh`; the defect is test-only, and the
issue says so up front.

**Acceptance.** `pytest plugin-tests/tests/hooks` green. `grep -rn '"python"'` over the test file
returns nothing. `plugin-tests/tests/consistency/test_subprocess_encoding.py` also reads test call
sites, so run `plugin-tests/tests/consistency` as well.

---

## B — #199: a row is recorded when HEAD did not move

**The issue's stated fix is not implementable as written — this document resolves that.**
"Capture HEAD before running the command" is a pre-command read, and `log-commit-provenance.py` is
wired on **PostToolUse only** (`hooks.json:86`). Its payload carries `tool_input` and `cwd`, no
pre-state. Adding a PreToolUse leaf that stashes HEAD would mean editing
`dispatch-bash-pretooluse.py` and adding a hook to an area with no mutant batches at all (#176), which
is not a lite change.

**Decided: two post-hoc checks that need no pre-state, both inside the existing hook.** Record only
when both hold:

1. **The reflog's top entry is a commit.** `git reflog -1 --format='%gs'` on HEAD returns
   `commit: …`, `commit (initial): …`, or `commit (amend): …` after a real commit, and something
   else — `checkout: moving from …`, `merge …`, `rebase …` — after anything that moved HEAD
   otherwise. Measured above.
2. **That sha is not already the last row in the ledger.** Read the final line of
   `commit-provenance.jsonl` and skip when its `sha` equals the HEAD about to be written.

**Why both, and what each one alone misses.** Measured above: after a `git commit` that stages
nothing, the reflog's top entry is *unchanged* — still the previous real commit — so check 1 alone
passes and the duplicate is written. That is the `f3735db`-recorded-three-times case, and check 2 is
what kills it. Check 2 alone misses the `b1bcd93` case, where the re-recorded sha is a merge commit
made days earlier on another branch and does not match the ledger's last row; check 1 kills that one,
because the reflog top there is a `checkout:` entry.

**Keep the failure posture.** Both checks are best-effort like everything else in the hook: a git
failure or an unreadable/absent ledger returns 0 and writes nothing rather than raising. Reading the
last line means seeking to the end, not loading a 145-line file into memory each commit — but do not
claim a performance number without running one.

**Out of scope.** Do not remove the pre-existing `a27bd85` duplicate pair at ledger lines 130–131.
#199 records it as out of scope and it stays that way; this candidate fixes the cause, and rewriting
history in a ledger is a separate, deliberate act.

**Acceptance.** `pytest plugin-tests/tests/hooks` green, with new tests covering each branch
separately: a real commit writes a row; a failed commit after a real one writes nothing (check 2);
a commit command run when HEAD last moved by checkout writes nothing (check 1). Three tests, because
one test passing both branches cannot tell which check did the work.

**Constraint on the run.** `mutants/hooks/` does not exist, so there is no batch to keep green and
none is owed here (#176 covers that debt). But this is a fix to a defect a review found, which
CLAUDE.md prices at "that area, plus a mutation batch over what the fix touches" — so plant the two
checks by hand at minimum: delete check 1, confirm a test fails; delete check 2, confirm a different
test fails. Do not run `mutate.py` while review agents read the tree.

---

## C — #200: a blank line before `Co-Authored-By` zeroes the count

**Decided. Take fix part 1 (say it where the trailers are written) and defer fix part 2 (the
guard).** Reason for the split is below; it is a real gap, not a tidy-up.

**What to do.** All five `Measured-by:` instruction sites state the trailer format and none mentions
`Co-Authored-By:` at all. Add, at each site that shows a `git commit` invocation
(`ship.md:68`–`:72`, `spec-to-pr/SKILL.md:121`, `lite-pr/SKILL.md:135`, `revise.md:208`): the
`Co-Authored-By:` / `Claude-Session:` lines go inside the **same** `-m` as the `Measured-by:` lines,
with no blank line between. Git parses trailers from the last paragraph only, so a blank line puts
every measurement outside the trailer block.

**Measured, so the prose is not reasoning about git.** The reproduction above: identical
`Measured-by:` lines parse as **2** values in one block and **0** with a blank line before
`Co-Authored-By:`.

**Why the wrong shape is the natural one.** The session-attribution guidance presents
`Co-Authored-By:` / `Claude-Session:` as *the message ending*, which invites appending it as its own
paragraph. That guidance is harness-supplied and not editable from this repo — which is exactly why
the skills have to state it.

**Out of scope, deferred with a reason.** Fix part 2 — a guard comparing `grep -c '^Measured-by:'`
over the message body against the trailer-parser count — is not in this candidate. It would be a new
hook file in `hooks/`, and CLAUDE.md prices a new hook at the full five checks in an area with no
mutant batches (#176). Prose alone closes this instance and not the class. **Say so in the PR body
and re-open the guard as its own issue** rather than letting the deferral go unrecorded.

**Do not correct the existing zeroed rows.** #197 (`1b02db5`) already corrected the 7 commits /
23 trailers it found; the 121 zeros in the current 145-row ledger are overwhelmingly genuine — most
commits assert no measurement — and there is no way to tell a genuine zero from a swallowed one
after the fact without re-reading each message. Editing them would be guessing.

**Acceptance.** `pytest plugin-tests/tests/conformance` green — `test_skill_lint.py` is the
`SKILL.md` frontmatter and reference-graph guard, so a link this edit adds that resolves to nothing
fails there. Run `plugin-tests/tests/consistency` too:
`test_measurement_names_its_command.py`'s `_FAMILY` literal names `spec-to-pr/references/revise.md`,
one of the four files this candidate edits. All five instruction sites state the same rule — do not
fix three of five.

---

## Out of scope — the other six open issues

**Unchanged from `open-issues-lane1-2026-09-02.md`; see that document for the full reasoning:**

- **#190** — the issue *is* the decision (which unscanned shipped file types to start scanning).
  `/cla:shape-decision`.
- **#175** — three open questions unanswered. `/cla:shape-decision`.
- **#176** — seven grandfathered guards, "which one is next" explicitly a judgement call. Also
  unsuited to an unattended chain: each batch needs `mutate.py` serialized against review agents.
- **#174** — blocked on run data this repo will never produce.
- **#179** — check the live vendored `openspec-propose` SKILL.md, then file upstream or close. No PR
  here either way.
- **#173** — a whole new skill plus two hook edits. The issue names its own route:
  `/cla:spec-to-pr`.

**Note the shape of the remainder.** After this batch, every open issue is either a shaping job or a
`spec-to-pr` job. There is no third lite lane waiting behind this one.
