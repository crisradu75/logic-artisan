# Which absolute rules could a hook or script enforce? (principle 3, 2026-11-18)

Principle 3 of `cla.io/decisions/cla-foundation-2026-11-17.md`: a rule that must never bend becomes a
hook or script; everything else is guidance. This inventory takes every `keep` entry in
`docs/rule-ledger.md` (450 on `main` at `dbb96143`) and asks what holds it today and what could.
Three Sonnet agents read each rule against the hook and script headers; the detail lists are below.
It proposes; nothing here is built. Which checks to build is the owner's decision.

## Counts

| Category | Rules | Meaning |
|---|---|---|
| judgement | 262 | needs reading or deciding: report wording, severity calls, what a user meant |
| script | 82 | a script at an existing skill step could check it from files, git state or a run record |
| hook | 64 | a PreToolUse hook could check it from the tool input, without judging intent |
| enforced | 25 | a shipped hook or script already holds it in a consumer repo |
| repo-test | 17 | only a `plugin-tests/` test holds it, so it holds in this repo, not in a consumer repo |

Counted with `grep -oE '^- (judgement|hook|script|enforced|repo-test)'` over the three detail lists.
Many of the 146 hook and script rules restate one mechanism, so they reduce to the 12 checks below.

## Proposed checks, ranked by protected area, then by rules covered

The rule counts are rough: the three lists overlap and were merged by hand.

| # | Check | Kind, size | Rules | Area |
|---|---|---|---|---|
| 1 | **`git add` scope:** warn or ask on `git add -A`, `--all`, `.`, a bare `openspec/` or a plugin-cache path. Warn, not block: a user's own `git add -A` is legitimate. | Bash hook, small | ~19 | user's files |
| 2 | **Chain head gate:** before a chain merges or resumes, compare the recorded `head_sha` with `git rev-parse HEAD`, `git status --porcelain`, `git ls-remote` and the PR head; refuse on a mismatch, a PR the chain did not open, or an open blocking finding. | script, medium to large (uses the existing chain ledger) | ~25 | user's files |
| 3 | **Ship preflight and push verification:** branch-collision checks, `HEAD` equal to `ls-remote` after each push, base freshness, and the `Measured-by` trailer count; one script replacing the command lists the skills repeat. | script, medium | ~15 | user's files, honesty |
| 4 | **Plugin-cache edits:** deny an Edit/Write under the installed plugin's cache directory (an overlay or a "fix" there is lost on the next update). | Edit/Write hook, small | ~7 | user's files |
| 5 | **cla-setup post-run diff:** after setup, assert that `CLAUDE.md`, `*.local.md`, `notes.md` and the terminology file are unchanged unless the owner said yes, and that no overlay was created. | script, small to medium | ~7 | user's files |
| 6 | **Overwrite guard:** ask before a Write replaces `settings.local.json` or an existing file under `cla.io/decisions/`, and merge permissions additively. High false-positive risk unless scoped to those paths. | Write hook plus a script, medium | ~5 | user's files, safe writes |
| 7 | **Commit honesty:** refuse `Measured-by: none`, an `--allow-empty` commit, and a staged `[DEBUG-` tag. | Bash hook, small | ~5 | honesty |
| 8 | **Bash text safety:** writes to `..`, a literal `${CLAUDE_PLUGIN_ROOT}/` in a command, a multi-line `--body`/`-m`, and a PR-body temp file inside the repo. | Bash hook, small | ~6 | safe writes |
| 9 | **Git and gh workflow:** `gh pr create` without `--base`, a bare `git worktree add`, a second `check_cite_drift.py --fix` run, a change folder left uncommitted before a worktree is cut. | hooks and script steps, small | ~7 | user's files |
| 10 | **Agent dispatch:** require `model` on every Agent call, flag diff text pasted into an Agent prompt, check that review agents get read-only tools, check that a sub-agent's reply carries its required `Scanned:` / `Fact corrections:` lines. Presence only, not truth. | Agent hooks plus a conformance test, small | ~7 | cost, honesty |
| 11 | **Secrets in a checkpoint:** scan a checkpoint Write for key prefixes, private-key headers and connection strings. Misses unusual secrets. | Write hook, small | 2 | security |
| 12 | **Small script steps:** an EnterWorktree path check, section counts, the `openspec validate` output, conflict markers left in a file. | script steps, small | ~5 | mixed |

## Gaps in what is enforced today

- `ask-destructive-git` does not cover a plain `git rebase`, or a `git switch <branch>` that would carry uncommitted work.
- `warn-stray-scratch-artifact` only warns.
- The 17 `repo-test` rules (for example the annotate server never writing the document, and the temp-dir isolation) hold in this repo's tests and nowhere in a consumer repo. That is fine where the rule is about the plugin's own code, which the tests do exercise.

## How sure this is

The agents judged most `judgement` rows from the ledger fragment, its file and the hook headers, not
from a full read of every rule, and one cited `repo-test` names without opening the tests. Treat
the counts as a sizing, not a proof. Each check above needs its rules re-read before it is built.

## Detail

One line per `keep` rule: `- <category> | <mechanism or reason> | <ledger fragment>`, by shipped file, then each group's own candidate list.

### Group a

#### README.md
- enforced | skill frontmatter `disable-model-invocation: true` stops natural-language start | so a description match must never start one.
- hook | PreToolUse Edit/Write: block a file_path under the plugin cache directory (version-keyed install copy); shared with 142 | Never edit it: it is a version-keyed cache
- judgement | output-style prose: what counts as evidence or meaning is a reading call | Never cut evidence: a file:line, a test result, real output.
- judgement | output-style prose: what counts as evidence or meaning is a reading call | Never trade correctness for brevity.
- judgement | output-style prose: what counts as evidence or meaning is a reading call | error text are quoted exactly, never shortened.
- judgement | honesty of a reported result; needs reading the run | could-not-run, which is never a pass.

#### output-styles/CLA.md
- judgement | output-style prose: what counts as evidence or meaning is a reading call | Cut recaps and preamble, never evidence.
- judgement | output-style prose: what counts as evidence or meaning is a reading call | Never at the cost of correctness.
- judgement | output-style prose: what counts as evidence or meaning is a reading call | Never shorten a code comment or a command, and never paraphrase an
- judgement | output-style prose: what counts as evidence or meaning is a reading call | Brevity never removes:
- judgement | wording of a question line; no mechanical signal for a vague pointer | The line never points with "it", "that PR" or "the statement".
- judgement | wording of a question line; no mechanical signal for a vague pointer | Never pick an older open question the reply might mean.
- judgement | output-style prose: what counts as evidence or meaning is a reading call | Never buy brevity by dropping words that carry meaning

#### output-styles/COPILOT.md
- judgement | Copilot-only stand-in rule on agent behaviour; no tool-call signal | never simulate a required delegation or chain silently.
- hook | PreToolUse Bash: block a command still holding a literal `${CLAUDE_PLUGIN_ROOT}/` path prefix (SKILL.md bodies arrive substituted, so a literal one is unresolved); shared with 121 | never run an unresolved placeholder.
- judgement | output-style prose: what counts as evidence or meaning is a reading call | Never omit a verification step or its result.

#### agents/doc-sweeper.md
- judgement | agent behaviour on an empty glob; the caller sees only the report | A supplied path or glob that resolves to ZERO files is never
- judgement | agent behaviour on an empty glob; the caller sees only the report | Never fall back to a different path shape (e.g. a repo-wide glob) if the caller
- judgement | whether each reported hit was literally matched needs re-running the search | every hit you report MUST carry the *actual matched line*
- judgement | whether each reported hit was literally matched needs re-running the search | Never report a hit you did not literally match, and never
- hook | PostToolUse Agent (subagent_type doc-sweeper): the returned text must hold a line starting `Scanned:`; checks the footer exists, not that its numbers are true | **Then, ALWAYS, one accounting footer line
- judgement | a count is true only if re-run; the footer hook cannot check the number | report the count your Grep actually returned, never an estimate.

#### agents/fact-gatherer.md
- judgement | caller-side duty to verify; no signal | The caller must verify those themselves.
- judgement | whether a row is fabricated needs reading it against the code | Never fabricate. If you cannot locate the target at all
- judgement | evidence quality per row; a regex finds a bare check mark but not a paraphrase | Every row MUST resolve to one of exactly two things, never a bare

#### com.github.copilot/agents/doc-sweeper.agent.md
- judgement | agent behaviour on an empty glob; the caller sees only the report | A supplied path or glob that resolves to ZERO files is never
- judgement | agent behaviour on an empty glob; the caller sees only the report | Never fall back to a different path shape (e.g. a repo-wide glob) if the caller
- judgement | whether each reported hit was literally matched needs re-running the search | every hit you report MUST carry the *actual matched line*
- judgement | whether each reported hit was literally matched needs re-running the search | Never report a hit you did not literally match, and never
- hook | PostToolUse Agent (subagent_type doc-sweeper): the returned text must hold a line starting `Scanned:`; checks the footer exists, not that its numbers are true | **Then, ALWAYS, one accounting footer line
- judgement | a count is true only if re-run; the footer hook cannot check the number | report the count your Grep actually returned, never an estimate.

#### com.github.copilot/agents/fact-gatherer.agent.md
- judgement | caller-side duty to verify; no signal | The caller must verify those themselves.
- judgement | whether a row is fabricated needs reading it against the code | Never fabricate. If you cannot locate the target at all
- judgement | evidence quality per row; a regex finds a bare check mark but not a paraphrase | Every row MUST resolve to one of exactly two things, never a bare

#### skills/checkpoint/SKILL.md
- hook | PreToolUse Edit/Write: scan the content written under `cla.io/checkpoints/` for high-signal secret shapes (key prefixes, private-key headers, `scheme://user:pass@`); would miss odd secrets | Points at commits and PRs; never copies secrets.
- hook | PreToolUse Edit/Write: scan the content written under `cla.io/checkpoints/` for high-signal secret shapes (key prefixes, private-key headers, `scheme://user:pass@`); would miss odd secrets | Never copy a token, key, connection string, or the

#### skills/codify-learnings/SKILL.md
- judgement | what a retro may propose is a decision, not a tool input | **Never propose edits to** a skill's bundled scripts
- script | codify-learnings archive step already counts `grep -c ^## ` before and after; a small script run at that step compares the two totals and exits non-zero | the total must match.

#### skills/codify-learnings/references/routing.md

#### skills/diagnose/SKILL.md
- judgement | a paired string across two files; only a repo-side test could pin it, none exists | a rename must touch both.

#### skills/diagnose/references/strategies.md

#### skills/feedback/SKILL.md
- judgement | user decision timing | Clearing `notes.md` afterward is the user's explicit call, never automatic.
- judgement | ordering inside the skill run | so it must run before the first note is captured
- judgement | skill-scope limit; the hook cannot tell which skill is active | **never edit or overwrite source files, never run the app**
- judgement | labelling a note as unconfirmed is wording | so it's never mistaken for a confirmed diagnosis
- judgement | whether two issues are distinct is a judgement | Never silently fuse two distinct issues.

#### skills/new-worktree/SKILL.md
- enforced | `block-worktree-path-escape.py` blocks Write/Edit that escape the worktree; file-writing Bash and Read are not covered | `Bash` call for the rest of the task must use a path relative to the worktree cwd
- enforced | `block-worktree-path-escape.py` blocks Write/Edit that escape the worktree; file-writing Bash and Read are not covered | never a hardcoded primary-clone path
- judgement | refusal recovery choice; renaming a directory has no reliable command shape | Never "fix" it by renaming
- judgement | content of the final report | the final report must say this mode was used.
- judgement | manual worktree mode: the session cwd is not the worktree, so no hook can tell which path is wrong | path must target the worktree explicitly

#### skills/new-worktree/references/path-casing.md
- judgement | content of the final report | **One thing genuinely changes, and it must go in the final report.**
- judgement | manual worktree mode: the session cwd is not the worktree, so no hook can tell which path is wrong | path must target the worktree explicitly. `block-worktree-path-escape.py` is no

#### skills/report-upstream/SKILL.md
- enforced | `check_no_project_tokens.py` fails on a project token in shipped text | Never hardcode one in this file: portable core must not name
- hook | PreToolUse Bash: a `gh ... --body "` or `git commit -m "` argument that holds a newline (or a `$(cat <<` heredoc) is refused with a pointer to `--body-file` / `-F` | Open it with a body file, never an inline multi-line string:

#### skills/right-model/SKILL.md

#### skills/save-permissions/SKILL.md
- hook | PreToolUse Write: ask when file_path is an existing `.claude/settings.local.json` or `settings.json` (merge goes through the script instead) | NEVER rewrite the full file via Write.
- judgement | how to work around an encoding problem is not a command shape | never invent character-code workarounds.

#### skills/shape-decision/SKILL.md
- judgement | stopping criterion for questions | Stop on clarity, never on a question count.
- judgement | what the skill reads is a decision | - Always: the repo's instruction files
- judgement | what the skill reads is a decision | The first three are always listed
- judgement | whether a fact dropped out needs comparing context | A fact already in hand must never silently drop out.
- hook | PreToolUse Write: block when file_path is an existing file under `cla.io/decisions/` (the skill must append `-2`, `-3`); needs the directory name fixed in the hook | append `-2`, `-3`, and so on; never overwrite.

#### skills/shape-decision/references/question-form.md

#### skills/spec-to-pr-retro/SKILL.md
- judgement | retro scope; the hook cannot tell the active skill | Never edit `openspec/**` or a script.

#### skills/_shared/README.md
- repo-test | `plugin-tests/tests/conformance/test_skill_lint.py` (named in the ledger origin) checks shipped skills use the plugin-root path | Always with the explicit plugin-root path, never a bare relative one

#### skills/_shared/references/base-branch-resolution.md
- judgement | base resolution is a step in a skill; wrong range only shows at run time | resolved — never assumed
- judgement | a hook could flag `master..` in a command but a repo whose default really is master would be falsely blocked | Never hardcode `master`

#### skills/_shared/references/bash-discipline.md
- hook | PreToolUse Bash: the whole forbidden-shapes list in one check: `cd &&` (already `block-cd-in-bash`), heredoc-subshell commit, multi-line `--body`, `git add -A`, writes to `..`; shared with 53, 66, 68, 73 | The skill MUST NOT emit them.
- hook | PreToolUse Bash: block a redirect (`>`, `>>`), `tee`, `cp`, `mv` or `mkdir` whose target starts with `../`; `block-worktree-path-escape` covers only Write/Edit | Never write to `..`, which in a consuming repo holds the user's other projects
- judgement | the scratchpad is outside the checkout and legitimate, so "outside" cannot be told from a wrong path by string | Never write them anywhere else outside the checkout.
- hook | PreToolUse Bash: a `git add` with `-A`, `--all`, `-a`, `.` or a bare `openspec`/`openspec/` operand is blocked or asked; none of the existing hooks check `git add` scope (warn-stray-scratch-artifact only reads status) | Always path-scope every staging call
- hook | PreToolUse EnterWorktree: check the `path` parameter lies under `.claude/worktrees/` of the same repo | `path` must be under `.claude/worktrees/` of the same repo
- judgement | needs state across calls (which commit follows a `--repo-root` use) | Every staging and commit call it guards must then use `git -C`
- judgement | intent behind adding a flag; no signal | Never add `--repo-root` to silence an exit 3
- enforced | `block-cd-in-bash.py` blocks `cd` directives, so the call must use absolute paths or `git -C` | Absolute paths everywhere — never rely on a prior `cd`
- hook | PreToolUse Bash: a `git add` with `-A`, `--all`, `-a`, `.` or a bare `openspec`/`openspec/` operand is blocked or asked; none of the existing hooks check `git add` scope (warn-stray-scratch-artifact only reads status) | **NEVER a broad `git add openspec/` for Archive**
- judgement | a broader parent versus a named path needs knowing what the change touched | name the specific source paths the change touched, never a broader parent
- hook | PreToolUse Bash: a `git add` with `-A`, `--all`, `-a`, `.` or a bare `openspec`/`openspec/` operand is blocked or asked; none of the existing hooks check `git add` scope (warn-stray-scratch-artifact only reads status) | archive commit. Never `git add -A`.
- hook | PreToolUse Bash: a `git add` with `-A`, `--all`, `-a`, `.` or a bare `openspec`/`openspec/` operand is blocked or asked; none of the existing hooks check `git add` scope (warn-stray-scratch-artifact only reads status) | never expand to `-A` or a bare `openspec/`
- judgement | reasoning step before using `--ours`/`--theirs` | never trust positional intuition about which side is "ours"
- judgement | reasoning step before using `--ours`/`--theirs` | Refer to the git man page when uncertain. Never assume.

#### skills/_shared/references/blocking-findings.md
- judgement | what is "the answer" in a finding triage is a decision | is an input to this filter, never the answer
- judgement | whether a finding names a protected area is a reading call | A finding that names a protected area is never non-blocking.
- judgement | whether a finding names a protected area is a reading call | It never says "nothing is protected".
- judgement | dispatch-time copy discipline; test pins the text, not the behaviour | pasted at dispatch time and never copied by hand into the brief
- repo-test | `test_cla_setup_rules_match_config.py` (named in `test_blocking_filter_single_source.py`) holds the floor in the copies of the protected list | The floor, always protected whatever the Stakes list says

#### skills/_shared/references/chain-merge.md
- judgement | what the orchestrator reads or derives is not a tool input | Never a re-derived branch name or an in-context number.
- judgement | a merge authorization widening is a reading of the user words; `ask-destructive-git` only asks before `gh pr merge` | **It never widens merging.**
- judgement | a question the user must answer; no mechanical signal | **The shared-state answer is never pre-answered.**
- judgement | whether a gate covers the item is a reading call | the item's review and full test gate must cover
- script | new chain-head check at chain-merge step: reads the notes row (`head_sha`, `branch`, `pr_number`), runs `git rev-parse HEAD`, `git status --porcelain`, `git ls-remote origin`, `gh pr view --json state,headRefOid` and exits non-zero on any mismatch; one script covers all these rules | `git rev-parse HEAD` must differ from the row's current `head_sha`
- script | new chain-head check at chain-merge step: reads the notes row (`head_sha`, `branch`, `pr_number`), runs `git rev-parse HEAD`, `git status --porcelain`, `git ls-remote origin`, `gh pr view --json state,headRefOid` and exits non-zero on any mismatch; one script covers all these rules | must be empty. Anything listed is part of
- script | new chain-head check at chain-merge step: reads the notes row (`head_sha`, `branch`, `pr_number`), runs `git rev-parse HEAD`, `git status --porcelain`, `git ls-remote origin`, `gh pr view --json state,headRefOid` and exits non-zero on any mismatch; one script covers all these rules | `git rev-parse HEAD` must equal `git ls-remote origin <branch>`.
- script | new chain-head check at chain-merge step: reads the notes row (`head_sha`, `branch`, `pr_number`), runs `git rev-parse HEAD`, `git status --porcelain`, `git ls-remote origin`, `gh pr view --json state,headRefOid` and exits non-zero on any mismatch; one script covers all these rules | **A resume never merges a moved head:**
- script | new chain-head check at chain-merge step: reads the notes row (`head_sha`, `branch`, `pr_number`), runs `git rev-parse HEAD`, `git status --porcelain`, `git ls-remote origin`, `gh pr view --json state,headRefOid` and exits non-zero on any mismatch; one script covers all these rules | `headRefOid` must equal `head_sha`; a different head means commits nobody tested
- script | new chain-head check at chain-merge step: reads the notes row (`head_sha`, `branch`, `pr_number`), runs `git rev-parse HEAD`, `git status --porcelain`, `git ls-remote origin`, `gh pr view --json state,headRefOid` and exits non-zero on any mismatch; one script covers all these rules | must be `OPEN`. `headRefOid`
- script | new chain-head check at chain-merge step: reads the notes row (`head_sha`, `branch`, `pr_number`), runs `git rev-parse HEAD`, `git status --porcelain`, `git ls-remote origin`, `gh pr view --json state,headRefOid` and exits non-zero on any mismatch; one script covers all these rules | `git rev-parse HEAD` must equal `head_sha`. If it
- script | new chain-head check at chain-merge step: reads the notes row (`head_sha`, `branch`, `pr_number`), runs `git rev-parse HEAD`, `git status --porcelain`, `git ls-remote origin`, `gh pr view --json state,headRefOid` and exits non-zero on any mismatch; one script covers all these rules | must be empty; anything listed would be tested by the gate below
- enforced | `ask-destructive-git.py` asks before a force-push; a plain rebase is not covered | Never rebase or force-push to clear it
- script | new chain-head check at chain-merge step: reads the notes row (`head_sha`, `branch`, `pr_number`), runs `git rev-parse HEAD`, `git status --porcelain`, `git ls-remote origin`, `gh pr view --json state,headRefOid` and exits non-zero on any mismatch; one script covers all these rules | `state` must be `MERGED`. Otherwise:
- judgement | which ref a diff uses is a reading call | after a fetch, never the local ref
- judgement | ALLOW_DESTRUCTIVE_GIT is legitimately typed by a user, so a hook cannot tell a chain setting it from a person | Never set `ALLOW_DESTRUCTIVE_GIT=1` to get one through.
- enforced | `hooks/git/pre-push` refuses a push to the default branch (needs the per-clone install) | Never push a fix to `<base-branch>`.

#### skills/_shared/references/conflict-resolution.md
- judgement | when an abort is right is a decision | never `--abort` reflexively
- judgement | when an abort is right is a decision | never as a shortcut past a two-line hunk
- script | `git_state.py` already detects an in-progress operation; adding the `git grep` conflict-marker scan to the precommit step would check it from files | `git grep -n '^<<<<<<<\|^=======\|^>>>>>>>'` must
- hook | PreToolUse Bash: a `git add` with `-A`, `--all`, `-a`, `.` or a bare `openspec`/`openspec/` operand is blocked or asked; none of the existing hooks check `git add` scope (warn-stray-scratch-artifact only reads status) | # never `git add -A`

#### skills/_shared/references/economy-rules-file.md
- repo-test | `test_review_sizing_single_source.py` and `test_cla_setup_economy_rules_file.py` pin the economy text copied into repos | Never cut these to save tokens.
- repo-test | `test_review_sizing_single_source.py` and `test_cla_setup_economy_rules_file.py` pin the economy text copied into repos | are never dropped in a rewrite
- repo-test | `test_review_sizing_single_source.py` and `test_cla_setup_economy_rules_file.py` pin the economy text copied into repos | always security, safe writes to a user's files and honesty claims
- judgement | test-time behaviour of writing to a user folder; no signal | never writing to a user's folders
- judgement | a contract-test design rule | a field that is optional upstream must be optional in
- judgement | a contract-test design rule | Never strip optionality from both sides

#### skills/_shared/references/instruction-files.md
- judgement | a question to the user before creating a file | Never create one silently.

#### skills/_shared/references/model-routing.md
- repo-test | `test_review_sizing_single_source.py` and `test_cla_setup_economy_rules_file.py` pin the economy text copied into repos | never fork the table
- judgement | dispatching phase duty | the dispatching phase always supplies the exact list
- repo-test | `test_review_sizing_single_source.py` and `test_cla_setup_economy_rules_file.py` pin the economy text copied into repos | at its final level and never lower; see
- repo-test | `test_review_sizing_single_source.py` and `test_cla_setup_economy_rules_file.py` pin the economy text copied into repos | and always security, safe writes to a user's files or honesty claims
- repo-test | `test_review_sizing_single_source.py` and `test_cla_setup_economy_rules_file.py` pin the economy text copied into repos | at round 1's final level, never lower (judged
- judgement | whether the session was in doubt cannot be measured | never the session's own sense that the call was close

#### skills/_shared/references/orchestration-economy.md
- repo-test | `test_review_sizing_single_source.py` and `test_cla_setup_economy_rules_file.py` pin the economy text copied into repos | to that gate but never shrink it.
- judgement | two suites running together needs process state, not a tool input | Never let two full suites run together.

#### skills/_shared/references/past-offenses.md
- judgement | where a lesson goes is a decision | `cla.io/lessons-learned/`, never here

#### skills/_shared/references/plugin-root.md
- hook | PreToolUse Bash: block a literal `${CLAUDE_PLUGIN_ROOT}/` expansion in a command; same check as 15 | never pass it through to a shell

#### skills/_shared/references/precheck.md
- judgement | scope of uncommitted work is a reading call | never sweeps another scope's uncommitted work
- hook | PreToolUse Bash: a `git add` with `-A`, `--all`, `-a`, `.` or a bare `openspec`/`openspec/` operand is blocked or asked; none of the existing hooks check `git add` scope (warn-stray-scratch-artifact only reads status) | beside the in-scope paths — never `-A`

#### skills/_shared/references/retiring-specs.md
- judgement | whether a restated requirement says the same outcome needs reading both | It must state the same outcome the old one did
- judgement | whether a restated requirement says the same outcome needs reading both | That change's brief must search the earlier tasks
- script | at the archive-prep step, run `openspec validate <change> --strict` and fail when its output holds `Archive would refuse this delta` (validate exits 0) | must match it exactly
- script | a step runs `openspec show <spec>` before and after the format fix and compares the requirement and scenario counts | the requirement and scenario counts must not change

#### skills/_shared/references/review-sweeps.md

#### skills/_shared/references/run-log-schema.md

#### skills/_shared/references/runtime-rules.md

#### skills/_shared/references/ship.md
- script | part of the ship preflight script: `git rev-parse --abbrev-ref <pr-base>@{u}` must succeed | The parent must exist on the remote
- script | new ship preflight script: the collision checks (`refs/heads`, `ls-remote`, `refs/remotes`, `rev-list --count` equal 0) read only git state; the same script covers all these | refs/heads/<branch>          # must be EMPTY
- judgement | what to do on an unanswered question is a decision | never create the branch on an unanswered question
- script | new ship preflight script: the collision checks (`refs/heads`, `ls-remote`, `refs/remotes`, `rev-list --count` equal 0) read only git state; the same script covers all these | must be 0 — no commits to lose
- script | new ship preflight script: the collision checks (`refs/heads`, `ls-remote`, `refs/remotes`, `rev-list --count` equal 0) read only git state; the same script covers all these | must be EMPTY — no remote branch to collide with
- script | new ship preflight script: the collision checks (`refs/heads`, `ls-remote`, `refs/remotes`, `rev-list --count` equal 0) read only git state; the same script covers all these | must be EMPTY — no local branch either
- hook | PreToolUse Bash on `git commit`: refuse when `git diff --cached` added lines hold a `[DEBUG-` tag | must return nothing; remove any tagged line before staging
- judgement | a string pair across two files; only a repo-side test could pin it, none exists | a rename must touch both, or this grep searches for a string nothing writes
- enforced | `warn-stray-scratch-artifact.py` warns on a scratch file at the repo root before `git add`/`git commit` (warning only) | Never fold it into the commit
- judgement | whether a delegate report is trusted is a decision | never skip this because Implement's delegate reported success
- hook | PreToolUse Bash on `git commit`: refuse a message holding `Measured-by: none` | never `Measured-by: none`
- judgement | whether two numbers came from one tree needs reading the claim | must come from one tree
- judgement | whether two numbers came from one tree needs reading the claim | and the trailer must name it
- hook | PreToolUse Bash: a `git add` with `-A`, `--all`, `-a`, `.` or a bare `openspec`/`openspec/` operand is blocked or asked; none of the existing hooks check `git add` scope (warn-stray-scratch-artifact only reads status) | Path-scoped staging — NEVER `git add -A`
- hook | PreToolUse Bash: block `git add` of a path inside the installed plugin cache; shared with the cache edit check on 2 | never a path in the installed plugin tree
- hook | PreToolUse Bash: a `git add` with `-A`, `--all`, `-a`, `.` or a bare `openspec`/`openspec/` operand is blocked or asked; none of the existing hooks check `git add` scope (warn-stray-scratch-artifact only reads status) | plugin tree). Never expand to `-A`.
- script | ship step 3 check: the two `Measured-by` counts (grep against git trailer parse) compared by a small script that exits non-zero when they differ | **Check that it parsed, before you push.** These must agree:
- script | ship step 3 check: `git rev-parse HEAD` compared with `git ls-remote origin <branch>` by a script; exit 1 prints `push not verified` | They must be equal. Different, non-zero

#### skills/_shared/references/skill-authoring.md
- enforced | `check_no_project_tokens.py` fails on a project token in shipped text | Never let a repo token land
- judgement | skill-authoring design rule about where an invariant sits | Each stub MUST be **self-sufficient for its own invariant**
- judgement | skill-authoring design rule about where an invariant sits | **Always stays inline:**
- judgement | skill-authoring design rule about where an invariant sits | this MUST be a hoisted one-liner
- hook | PreToolUse Bash: a `git add` with `-A`, `--all`, `-a`, `.` or a bare `openspec`/`openspec/` operand is blocked or asked; none of the existing hooks check `git add` scope (warn-stray-scratch-artifact only reads status) | never `git add -A` / path-scoped staging
- judgement | skill-authoring design rule about where an invariant sits | never swap in a sibling's
- judgement | skill-authoring design rule about where an invariant sits | Never relocate an invariant to shrink the file
- enforced | `check_no_project_tokens.py` fails on a project token in shipped text | check_no_project_tokens.py` MUST **exit 0**
- judgement | a test of whether the reader can answer; no signal | the reader must be able to answer

#### skills/_shared/references/subagent-brief.md
- judgement | how a fix brief is split is a writing choice | authority and must not arrive as one instruction.
- enforced | `ask-destructive-git.py` asks before `git checkout`/`restore <path>` over dirty files and forced `switch`/`checkout`; a plain `git switch <branch>` is not covered, and the hook cannot tell a reviewer subagent from the session | and never `git checkout`, `git switch`
- judgement | which line number a reviewer counts is a reading call | never a line counted inside the diff file
- judgement | review brief wording | The list never suppresses a Critical security, money or data-loss finding.
- judgement | review brief wording | Report those always, flagged as overriding the stated constraints
- hook | PostToolUse Agent: when the dispatch prompt names `Fact corrections:`, the returned text must hold that field, checked by string match; not a check that its content is right | Never omit the field.
- judgement | whether the orchestrator ran a check is not recorded as a tool input | the orchestrator must have RUN it and seen it exhibit the defect
- judgement | how a stall was inferred is not observable | Never infer it from elapsed time or a guess.
- judgement | what status a delegate gives is a reading call | is `blocked`, never `done`.
- judgement | needs knowing which stops were sanctioned; run record alone does not say | the run record must show it as

#### skills/_shared/references/terminology-format.md
- judgement | a skill reading the glossary; no tool-call signal | own glossary of that kind is never read or changed
- judgement | skill behaviour on a missing file | **Absent is never an error**

#### Candidates

##### 1. Bash `git add` scope check (hook, small)
PreToolUse Bash: refuse (or ask) a `git add` carrying `-A`, `--all`, `-a`, `.` or a bare `openspec`/`openspec/` operand, or a path inside the plugin cache. None of the existing Bash hooks reads `git add` scope. Rules covered: bash-discipline.md (`Always path-scope every staging call`, `**NEVER a broad git add openspec/ for Archive**`, `archive commit. Never git add -A.`, `never expand to -A or a bare openspec/`), conflict-resolution.md (`# never git add -A`), precheck.md (`beside the in-scope paths — never -A`), ship.md (`Path-scoped staging — NEVER git add -A`, `plugin tree). Never expand to -A.`, `never a path in the installed plugin tree`), skill-authoring.md (`never git add -A / path-scoped staging`). Protected area: user's files (a parallel session's uncommitted files swept into a commit). Size: small, one function in `dispatch-bash-pretooluse.py`.

##### 2. Bash writes outside the checkout (hook, small)
PreToolUse Bash: refuse a redirect, `tee`, `cp`, `mv` or `mkdir` whose target begins with `../`. Covers bash-discipline.md `Never write to ..` and part of `The skill MUST NOT emit them.` Protected area: user's files. Size: small.

##### 3. Literal `${CLAUDE_PLUGIN_ROOT}/` in a command (hook, small)
PreToolUse Bash: refuse a command holding the unexpanded placeholder as a path prefix. Covers plugin-root.md `never pass it through to a shell` and COPILOT.md `never run an unresolved placeholder.` Protected area: safe writes (a command runs against `/skills/...`). Size: small; risk is a diagnostic `echo` of the variable, so match only the `/` prefixed form.

##### 4. Chain head check (script, medium)
A script run at the chain-merge steps. It reads the notes row (`head_sha`, `branch`, `pr_number`), runs `git rev-parse HEAD`, `git status --porcelain`, `git ls-remote origin <branch>` and `gh pr view --json state,headRefOid`, and exits non-zero on a mismatch. Covers chain-merge.md: `git rev-parse HEAD must differ from the row current head_sha`, `must be empty. Anything listed is part of`, `git rev-parse HEAD must equal git ls-remote origin <branch>.`, `A resume never merges a moved head:`, `headRefOid must equal head_sha`, `must be OPEN. headRefOid`, `git rev-parse HEAD must equal head_sha. If it`, `must be empty; anything listed would be tested`, `state must be MERGED. Otherwise:`. Protected area: user's files (merging a head nobody reviewed). Size: medium (parses the notes table).

##### 5. Ship preflight and verification script (script, medium)
One script for ship.md: branch collision and rename-in-place checks (`refs/heads`, `ls-remote`, `refs/remotes`, `rev-list --count` is 0, parent upstream exists), then after the push, `HEAD` equals `ls-remote` and the two `Measured-by` counts agree. Covers ship.md `The parent must exist on the remote`, `refs/heads/<branch> # must be EMPTY`, `must be 0 — no commits to lose`, both `must be EMPTY` lines, `**Check that it parsed, before you push.**`, `They must be equal. Different, non-zero`. Protected area: user's files, honesty. Size: medium.

##### 6. Commit-message and staged-diff checks (hook, small)
PreToolUse Bash on `git commit`: refuse `Measured-by: none` in the message, and a staged diff whose added lines hold `[DEBUG-`. Covers ship.md `never Measured-by: none`, `must return nothing; remove any tagged line before staging`. Protected area: honesty, user's files. Size: small (runs `git diff --cached`).

##### 7. Multi-line argument shapes (hook, small)
PreToolUse Bash: a `gh pr create|edit --body "..."` or `git commit -m "..."` argument holding a newline or a `$(cat <<` heredoc. Covers report-upstream `never an inline multi-line string:` and part of bash-discipline `MUST NOT emit them.` Protected area: safe writes. Size: small; shares the quote walker with `warn-heredoc-escape-mangling.py`.

##### 8. Settings and decision file overwrite (hook, small)
PreToolUse Write: ask when the target is an existing `.claude/settings.local.json`/`settings.json`, and block an existing file under `cla.io/decisions/`. Covers save-permissions `NEVER rewrite the full file via Write.` and shape-decision `append -2, -3, and so on; never overwrite.` Protected area: user's files. Size: small; the directory name must be fixed in the hook.

##### 9. Plugin cache edit (hook, small)
PreToolUse Edit/Write: block a file_path inside the plugin cache directory. Covers README `Never edit it: it is a version-keyed cache`. Protected area: user's files / safe writes. Size: small.

##### 10. Checkpoint secrets scan (hook, small-medium)
PreToolUse Edit/Write for files under `cla.io/checkpoints/`: refuse content matching key prefixes, private-key headers or `scheme://user:pass@`. Covers checkpoint `Never copy a token, key, connection string`, `never copies secrets`. Protected area: security. Size: small; pattern list will miss unusual secrets, so it backs the rule rather than replacing it.

##### 11. Sub-agent return format (hook, small)
PostToolUse Agent: doc-sweeper return must contain a line starting `Scanned:`; a fact-fix return must contain `Fact corrections:` when the dispatch prompt names it. Covers both doc-sweeper `ALWAYS, one accounting footer line` entries and subagent-brief `Never omit the field.` Protected area: honesty. Size: small; checks presence only.

##### 12. Smaller script steps (script, small)
EnterWorktree `path` under `.claude/worktrees/` (hook on EnterWorktree, covers bash-discipline `path must be under .claude/worktrees/`); codify-learnings `## ` count before/after; `openspec validate` output holding `Archive would refuse this delta`; `openspec show` counts before/after the format fix; `git grep` conflict markers added to the pre-commit step.

### Group b

#### Principle 3 classification, sections test-quality-gates.md through multi-pr/references/cleanup.md

#### skills/_shared/references/test-quality-gates.md
- judgement | test-writing doctrine, read by a human reviewer | A non-vacuity floor must track its population
- judgement | needs comparing a floor to its population by reading | a deletion. And **never lower a
- judgement | wording about claims | Never quote a repo's current
- judgement | design doctrine | An alarm must be able to fire at the volume it will really see
- judgement | how to plant a failure; needs reading the test | The plant must land on the tested value
- judgement | needs reading the test | it must name the value
- judgement | process step, no signal | the step most worth never skipping

#### skills/_shared/references/test-quality.md

#### skills/spec-to-pr/SKILL.md
- judgement | agent behaviour; no tool input shows an assumption | resolved once at the start of the run, never assumed
- judgement | prose about how to name; a hook cannot know the resolved branch is wrong | Never spell `feature/<change-name>`
- judgement | report wording | Handoff never prints a bare `gh pr merge` for a stacked child
- hook | M1 Bash PreToolUse: `git add` with -A/--all/.//bare `openspec/` (shared by every broad-staging rule) | **Never run `git add -A`. Stage named paths only:**
- hook | M1 Bash PreToolUse: `git add` with -A/--all/.//bare `openspec/` (shared by every broad-staging rule) | per capability the change modifies, never `openspec/`
- script | M4 staged-scope check: staged paths (`git diff --cached --name-only`) vs the paths the step expects | An untracked file never rides into a commit it does not belong to
- judgement | how the agent reads git_state's exit code | never special-case "exit 1 is probably fine"
- enforced | hooks/ask-destructive-git.py asks before any `gh pr merge` (inline ALLOW_PR_MERGE=1 is the only bypass) | **Development only.** Never `gh pr merge`
- script | M5 settings merge: a stdlib script that merges required-permissions.json into settings.local.json additively, instead of an Edit | **additive only**, never removing or rewriting another key
- judgement | whether a question was asked cannot be read from a tool call | never a silent decision; do not proceed until answered
- hook | M8 Bash PreToolUse: `git worktree add ... -b` whose start point is not `origin/<ref>` | never off the primary clone's local ref
- judgement | how the agent reads an empty output | a `merge-base` that prints nothing is a Handoff Issue, never an empty list. Not `<base-branch>`
- judgement | how the agent reads an empty output | a `merge-base` that prints nothing is a Handoff Issue, never an empty list): Ship
- judgement | a Test-phase verdict from reading the plan | **Source changes but no commands named → `warn`, never `skip`**
- judgement | gate choice by reading the plan | a smoke pass never skips `full`
- hook | M1 Bash PreToolUse: `git add` with -A/--all/.//bare `openspec/` (shared by every broad-staging rule) | each touched `openspec/specs/<cap>/`, never `openspec/`
- judgement | step order; the probe emits no review field | always run the checklist's Step 2b, whatever the probe says

#### skills/spec-to-pr/references/archive.md
- hook | M1 Bash PreToolUse: `git add` with -A/--all/.//bare `openspec/` (shared by every broad-staging rule) | **Stage the named path groups, NEVER a broad `git add openspec/`.**
- script | M4 staged-scope check at Archive: staged paths vs the closed list of allowed path groups | Every staged path in `git diff --name-only --cached` must match one of:
- script | M4 staged-scope check at Archive: each `changes/<n>/specs/<cap>` has `openspec/specs/<cap>/spec.md` staged | every capability under the change's `specs/` must have its `openspec/specs/<cap>/spec.md` staged
- hook | M1 Bash PreToolUse: `git add` with -A/--all/.//bare `openspec/` (shared by every broad-staging rule) | A path you missed is added alone (never `openspec/`, never `-A`)
- script | M2 push post-check: one script runs the four commands (branch, HEAD, @{u}, `gh pr view --json commits`) and exits non-zero on mismatch | # must equal <branch>
- script | M2 push post-check (same script) | # must equal the captured HEAD sha
- script | M2 push post-check (same script) | # the captured HEAD sha must appear in the returned commits[]
- script | M2 push post-check (the script's exit decides the mark; the marking itself is the agent's) | Never mark Archive `✓` on the local file moves or a 0-exit push alone.

#### skills/spec-to-pr/references/branch-and-pr-base.md
- hook | M6 Bash PreToolUse: `gh pr create` without `--base` | `gh pr create` MUST pass `--base <pr-base>` explicitly
- judgement | report wording | next-steps must NOT print the bare `gh pr merge` line for a stacked child
- hook | M7 extend warn-stacked-pr-merge.py: `gh pr merge --squash` while open PRs are based on the head branch | Use a **merge commit, never a squash**, on a stack.

#### skills/spec-to-pr/references/concurrent-runs.md
- judgement | where the session runs is not in any tool input | so the session itself must live in the worktree
- hook | M8 Bash PreToolUse: bare `git worktree add ... -b` (skills use manual_worktree.py via subprocess, which the hook never sees) | never bare `git worktree add ... -b <branch>`
- script | M9 probe: `git cat-file -e HEAD:openspec/changes/<name>` before the worktree is cut (probe_state.py or the recipe) | the change dir must already be committed

#### skills/spec-to-pr/references/design-tradeoffs.md

#### skills/spec-to-pr/references/handoff.md
- judgement | where the agent puts its report | as rendered Markdown in the assistant turn — never a file or a script
- judgement | report content | Also, always when they apply
- judgement | report structure | **split into three named subsections, always, even when empty:**
- judgement | report wording | is shown as ⚠ and never gets a bare merge line
- judgement | report wording | (`--pr-base` passed):** never a bare merge command
- judgement | how the agent builds a record | from the entries written as each round closed — never reconstructed here
- judgement | log_run.py checks shape, not whether the value is true | never guess `protected`, and never drop the round

#### skills/spec-to-pr/references/implement-delegate.md
- judgement | brief is prose in an Agent prompt | The brief MUST enumerate **every** task
- judgement | how the agent reads a delegate's return | **A return carrying no status token is `blocked`, never `done`.**
- judgement | agent bookkeeping | the event MUST be recorded as a Handoff Issue

#### skills/spec-to-pr/references/revise.md
- judgement | whether the user agreed to the spend is not in the tool input | never start a `Workflow` without it
- judgement | review level is a judgement call | A later round never uses a lower level than round 1.
- hook | M10 PreToolUse on the Agent tool: reject or warn when the parameters carry no `model` | Pass `model:` on EVERY dispatch, never relying on the toolkit file
- judgement | cannot tell which agent runs a command; ask-destructive-git only covers dirty-path checkout/restore | run no git command (not `git diff`, and never `git checkout`
- judgement | meaning of a line number in a finding | never a line counted inside the diff file
- hook | M11 PreToolUse on Agent: prompt carries diff text (a `diff --git ` header) instead of a path | **Write the diff to a file; pass its path, never the text.**
- judgement | no marker says which file is the diff file | never inside the working tree, where `git status` shows it
- hook | M11 PreToolUse on Agent: prompt carries diff text (`diff --git ` header) | Each prompt names its diff file's absolute path (never the diff text)
- judgement | severity ordering by reading | a Critical is never displaced by a lower-severity
- judgement | reporting | A crashed reviewer never vanishes silently.
- judgement | whether a review ran | **Round 1 always happens.**
- judgement | review level | at round 1's final level (never lower)
- judgement | path of a file the agent chose | never in the tree), name that file's absolute path
- judgement | verdict wording | never review nothing and call it clean
- judgement | verdict wording | never a skipped step
- judgement | severity call | is triaged at the **higher** severity, always.
- judgement | finding outcome | A blocking finding never exits "unaddressed".
- judgement | finding outcome | Never record it as Applied.
- judgement | report structure | three named subsections, never one bucket
- judgement | who does the check | that is never delegated.**
- judgement | delegate protocol wording | never the two-status `done`/`blocked` form
- judgement | bookkeeping | Never recorded as a delegate failure.
- judgement | how a return is read | **Never read a missing `Fact corrections:` field as `(none)`.**
- judgement | reporting | recover inline, but never silently
- judgement | finding bookkeeping | a finding never silently evaporates
- judgement | finding bookkeeping | never because an edit was made where the finding pointed
- judgement | a legitimate command on tracked files; the failure is on uncommitted dirs and is visible | Never `git show HEAD:<path>`
- judgement | no signal marks a copy as a backup | Never put a backup anywhere else outside the
- judgement | a delegate's behaviour | It mutates a scratchpad copy, never the live file.
- hook | M1 Bash PreToolUse: `git add` with -A/--all/.//bare `openspec/` (shared by every broad-staging rule) | stage the explicit changed paths (never `-A`)
- script | M3 staging check: after `git add -- <paths>`, a script fails when `git diff --cached --name-only` is empty | **`git diff --cached --name-only` must list at least one path.
- judgement | how the agent classifies a round | never by "zero findings triaged Applied"
- hook | M12 Bash PreToolUse: `git commit --allow-empty` | Never manufacture an empty commit for the counter.
- enforced | lib/log_run.py refuses a spec-to-pr-runs record missing a required field (ROUND_TRIGGERS shape check) | never drop the field to clear a refusal
- judgement | how the agent builds a record | it is never reconstructed there
- judgement | counts held in the agent's context | both must be zero to exit clean

#### skills/spec-to-pr/references/test-notes.md

#### skills/lite-pr/SKILL.md
- judgement | plan content | The plan MUST explicitly list, alongside the code files to change:
- judgement | spec-to-pr legitimately writes there; the hook cannot tell which skill runs | Never create a delta file, never touch `openspec/changes/`.
- judgement | how the agent reads an exit code | never infer "probably fine" on a non-zero exit
- judgement | cannot tell which agent runs a command; ask-destructive-git only covers dirty-path checkout/restore | run no git command (not `git diff`, and never `git checkout`
- judgement | meaning of a line number in a finding | never a line counted inside the diff file

#### skills/lite-pr/references/diagnose-escalation.md
- judgement | count of edit rounds is agent state | never another edit round
- judgement | whether a user is present is not in any tool input | never put a question mid-chain to a user who is not there

#### skills/lite-pr/references/measured-by.md
- hook | M13 Bash PreToolUse: `git commit` whose message contains `Measured-by: none` | never `Measured-by: none`
- judgement | needs judging two numbers | "no regression" — must come from one tree
- judgement | needs reading the trailer | and the trailer must name it
- script | M14 trailer parse check: count `^Measured-by:` lines vs git's parsed trailers on HEAD; run in the git pre-push hook or as a script at Ship | must agree — what you wrote against what git's parser sees

#### skills/lite-pr/references/mutation-gate.md
- judgement | no signal marks a copy as a backup | Never put a backup anywhere else outside the checkout.
- judgement | a delegate's behaviour | scratchpad copy, never the live file.

#### skills/lite-pr/references/review-fix-weight.md

#### skills/multi-pr/SKILL.md
- enforced | `disable-model-invocation: true` in multi-pr/SKILL.md frontmatter, held by the harness (consumer-side) | Merges pull requests, so it must never self-trigger on a description match
- judgement | agent behaviour | means THIS repo's default branch, resolved — never assumed
- judgement | a Stop hook cannot tell a finished chain from an idle one without chain state | **Never end a turn with nothing in flight.**
- hook | M1 Bash PreToolUse: `git add` with -A/--all/.//bare `openspec/` (shared by every broad-staging rule) | **Never run `git add -A`.** Same rule as `/cla:spec-to-pr`
- enforced | hooks/ask-destructive-git.py reads ALLOW_DESTRUCTIVE_GIT only from the session environment, which an agent's command cannot set | Never `ALLOW_DESTRUCTIVE_GIT=1`.
- judgement | how the agent reads an exit code | a non-zero exit halts and surfaces — never special-case it
- judgement | blocker classification | halts the chain; a content finding never does.
- judgement | whether a PR is the chain's own is a run fact (`gh pr merge` itself is asked by ask-destructive-git) | is outside this run: never merge, rebase or push it as part of the chain
- judgement | decision to ask | **A dependency cycle is never guessed past** — it's always its own explicit question
- judgement | decision to ask | **A prerequisite the chain cannot supply is never guessed past either.**
- judgement | run fact | since the chain never merges a PR it did not open
- judgement | decision to ask | except the cycle question, which is never skipped
- judgement | decision to ask | the closed blocker list above — never guess past one
- judgement | blocker classification | Tier B (content findings) never does.**
- judgement | status call | A change never counts done while a Deferred-Known-Issue
- script | M15 check_cite_drift.py: record the start commit and a `--fix` sentinel beside the artifacts; refuse a second `--fix` or a different start commit | Never run the recheck twice on one change: its fixes would move again.
- script | M16 chain-merge head guard: compare `gh pr view --json headRefOid` with the head recorded in the running notes (needs the recorded head, so a small run record) | **Never merge a head the change's review and full gate did not cover:**
- judgement | session behaviour | a fresh session always re-asks, since it has no way to know

#### skills/multi-pr/references/change-loop.md
- script | M16 chain-merge head guard (same check) | a moved head is never merged (`chain-merge.md`, "Record the head")
- judgement | finding status | **Never infer them fixed.**
- script | M15 check_cite_drift.py sentinel (same check) | **Never run it twice on one change.**
- script | M15 check_cite_drift.py: refuse a start commit different from the one recorded on the first run | Never substitute today's `origin/<base-branch>`.
- judgement | policy call on a finding | Never merge past it on the grounds that the policy is loose.
- judgement | how the agent reads output | never read its empty output as "all gone".
- enforced | hooks/git/pre-push blocks pushes to the default branch (once installed per clone) | never push to `<base-branch>`: follow `chain-merge.md`
- judgement | reporting | name it in the running notes and the final report, and continue — never accept it silently.
- judgement | wording of a record | it is written as the DERIVATION, never the bare word.**
- enforced | ask-destructive-git.py asks on force-push; a rebase is not covered | (never a rebase or force-push)
- judgement | retry intent | Never retry a merge hoping for green.
- script | M15 check_cite_drift.py: store the first run's result and read it back | never from a new run of the script
- judgement | the notes file name is not fixed; `git add` of it is not distinguishable from other paths | gitignored, never added or committed.

#### skills/multi-pr/references/cleanup.md
- judgement | how the agent builds a comparison | never compare a full clone under the worktrees folder with itself
- enforced | hooks/block-unsafe-recursive-delete.py blocks recursive delete whose target is a symlink or junction | Never `rm -r` or `rm -rf` the link in Git Bash.
- enforced | hooks/block-unsafe-recursive-delete.py (PowerShell Remove-Item form) | In PowerShell, never combine `-Recurse` with `-Force`
- enforced | hooks/ask-destructive-git.py asks on `git branch -D` and its spellings | never retry with `-D`.

#### Candidates

##### M1 Broad-staging guard (hook, small)
Bash PreToolUse (in the dispatcher, beside warn-stray-scratch-artifact's `git add` parse): warn or ask on `git add` with `-A`, `--all`, `-u`, a bare `.`, or a bare `openspec/`. Covers spec-to-pr SKILL "Never run `git add -A`", "per capability ... never `openspec/`", "each touched `openspec/specs/<cap>/`, never `openspec/`"; archive "NEVER a broad `git add openspec/`" and "never `openspec/`, never `-A`"; revise "(never `-A`)"; multi-pr SKILL "Never run `git add -A`". Area: user's files. Seven rules. Caveat: it also fires on a user's own `git add -A`, so warn rather than block.

##### M2 Archive push post-check (script, medium)
One stdlib script runs the four archive commands (branch name, HEAD, `@{u}`, `gh pr view --json commits`) and exits non-zero on any mismatch. Covers the four "must equal / must appear" lines and "Never mark Archive `✓` ... alone" (archive.md). Area: honesty. Five rules.

##### M3 Empty-staging check (script, small)
After `git add -- <paths>`, fail when `git diff --cached --name-only` is empty. Covers revise "must list at least one path". Area: honesty.

##### M4 Staged-scope check (script, medium)
Compare staged paths with the expected groups (the change's own paths, the `openspec/specs/<cap>/` of each capability under `specs/`). Covers archive "Every staged path ... must match one of", "every capability ... spec.md staged", and spec-to-pr SKILL "An untracked file never rides into a commit". Area: user's files. Three rules.

##### M5 Additive settings merge (script, medium)
A script merges required-permissions.json into `.claude/settings.local.json` additively instead of an `Edit`. Covers spec-to-pr SKILL "additive only, never removing or rewriting another key". Area: safe writes (the user's settings).

##### M6 `gh pr create` needs `--base` (hook, small)
Bash PreToolUse: warn when `gh pr create` has no `--base`. Covers branch-and-pr-base "MUST pass `--base <pr-base>`". Area: user's files.

##### M7 Squash on a stack (hook, small)
Extend warn-stacked-pr-merge.py to also warn on `--squash` when open PRs are based on the head branch. Covers "merge commit, never a squash, on a stack". Area: user's files.

##### M8 Bare `git worktree add` (hook, small)
Bash PreToolUse: warn on `git worktree add -b` whose start point is not `origin/<ref>`. Covers concurrent-runs "never bare git worktree add" and spec-to-pr SKILL "never off the primary clone's local ref". Area: user's files. Skills run manual_worktree.py through a subprocess, which the hook never sees, so only hand-typed use is caught.

##### M9 Change dir committed before worktree (script, small)
`git cat-file -e HEAD:openspec/changes/<name>` in probe_state.py or the worktree recipe. Covers concurrent-runs "the change dir must already be committed". Area: shipped to other repos.

##### M10 Agent dispatch carries `model` (hook, small-medium)
PreToolUse on the Agent tool: warn or deny when the parameters have no `model`. Covers revise "Pass `model:` on EVERY dispatch". Area: money/cost. Does not reach Workflow scripts.

##### M11 Diff text in an Agent prompt (hook, small)
PreToolUse on Agent: warn when the prompt contains a `diff --git ` header (diff text instead of a path). Covers revise "Write the diff to a file; pass its path, never the text" and "Each prompt names its diff file's absolute path". Area: shipped to other repos. Approximate signature; confidence medium.

##### M12 Empty commit (hook, small)
Bash PreToolUse: warn on `git commit --allow-empty`. Covers revise "Never manufacture an empty commit". Area: honesty.

##### M13 `Measured-by: none` (hook, small)
Bash PreToolUse: warn when a `git commit` message contains `Measured-by: none`. Covers measured-by "never `Measured-by: none`". Area: honesty.

##### M14 Trailer parse check (script, small)
Count `^Measured-by:` lines in HEAD's message against git's parsed trailers. Run at Ship or in hooks/git/pre-push. Covers measured-by "must agree". Area: honesty.

##### M15 Cite recheck run-once (script, small-medium)
check_cite_drift.py records the start commit and a `--fix` sentinel beside the artifacts, refuses a second `--fix` or a different start commit, and returns the stored result. Covers multi-pr "Never run the recheck twice", change-loop "Never run it twice", "Never substitute today's `origin/<base-branch>`", "never from a new run of the script". Area: safe writes. Four rules.

##### M16 Chain-merge head guard (script, large)
Compare `gh pr view --json headRefOid` with the head recorded in the running notes at review and full gate time; refuse the merge when they differ. Needs the recorded head. Covers multi-pr SKILL "Never merge a head the change's review and full gate did not cover" and change-loop "a moved head is never merged". Area: user's files. Two rules.

### Group c

#### skills/multi-pr/references/discover-and-gate.md
- script | at the merge step, compare the PR number to the ledger of PRs this chain opened (large: ledger read) | The chain never merges a PR it did not open
- judgement | deciding what counts as the dependency graph needs reading change references | `depends_on` is a hint, never the dependency graph.**
- judgement | how ordering and prerequisites were discovered is not visible in any file | Never use it as the sole source for ordering or prerequisite discovery
- judgement | whether the check was run is not recorded anywhere to read | The check is never optional, whether or not this repo has hit the gap before.
- judgement | which AskUserQuestion call a question goes in is not in any tool input a check can judge | **Always ask, batched into one `AskUserQuestion` call:**
- judgement | whether a NO shows its derivation is wording | **A NO carries its derivation, never the bare word.**
- judgement | phase ordering is the agent's sequencing, no record to read | both must land before Phase 2 starts
- judgement | which questions occupy a slot is a reading of the call content | They never take a slot in the always-ask call
- hook | PreToolUse on AskUserQuestion mid-chain; but "outside the closed blocker list" needs judging the question, so only approximable | never emit a mid-chain `AskUserQuestion` outside the closed blocker list

#### skills/multi-lite/SKILL.md
- judgement | self-trigger is a model-invocation setting (frontmatter `disable-model-invocation`, already set); the rule's prose part is not checkable | Opens and merges pull requests unattended, so it must never self-trigger on a
- script | probe/resolve default branch via git_state.py instead of assuming; check is whether a resolved name was used | means THIS repo's default branch, resolved — never assumed
- judgement | "turn ends with nothing in flight" is a model turn property; no hook sees it reliably | **Never end a turn with nothing in flight.**
- hook | Bash PreToolUse: block `git add -A`, `git add --all`, `git add .` (shares one mechanism with the same rule in multi-spec) | **Never run `git add -A`.** Same rule as `/cla:lite-pr`
- judgement | whether a gate had test commands is a reading of the gate | A gate with no test commands to run blocks the merge; it is never a pass.
- judgement | behaviour choice between halt and continue | never substitute whole-chain-halt behavior here
- script | a merge step could refuse when the ledger row has an unresolved blocking finding (needs ledger with finding state; shares the merge-gate script) | **Never merge a candidate carrying an unresolved blocking finding**
- judgement | whether the agent re-derived or read the file back is not visible | so a re-derived guess is never a substitute for reading this file back
- script | resume step reads the ledger row's `review` field; refuse to proceed when the row lacks an explicit clean (ledger read) | **Resume never infers clean:**
- script | resume compares PR head SHA (`gh pr view`) to the ledger's tested head before merge (same check as other moved-head rules) | **Resume never merges a moved head either:**
- script | the same ledger-vs-head comparison, with a missing ledger yielding the stated status | `head unverifiable (ledger lost)`, never merged

#### skills/multi-lite/references/bootstrap-and-tracking.md
- script | branch-off step could run `git_state.py` to confirm the branch base is the current remote base tip | Each candidate's `/cla:lite-pr` run must branch off an up-to-date `<base-branch>`.
- hook | Write PreToolUse on the ledger path when the file already exists and the content drops existing rows (approximate); overwrite-vs-reuse is mostly a step choice | reuse it, never overwrite it
- script | a ledger validator at resume: every row must carry `deferred` | A row missing `deferred` can never resume as clean.

#### skills/multi-lite/references/candidate-extraction.md
- judgement | whether a stated path was honoured needs reading the user text | a path the doc or the user states always wins.
- judgement | quality of the justification wording | the doc section read and what it describes — never a bare "no".
- script | same merge-gate ledger check as above (blocking-finding state) | never merge a candidate with an unresolved blocking finding

#### skills/multi-lite/references/candidate-loop.md
- judgement | identifying a PR by number vs branch is how the agent calls `gh`; a Bash hook could flag `gh pr view <branch>` but legitimate lookups exist | never by branch or title, which can match a different PR
- script | same moved-head ledger comparison | **A resume never merges a head this run did not test and review.**
- judgement | step flow of the agent | it never re-enters step 7 or step 8
- judgement | clean must come from recorded evidence, a reading of findings | **Never infer clean.**
- hook | Bash PreToolUse: flag a `git merge-base`/pull/`rev-list` command that names `<base-branch>` literally where a remote ref is expected; too tied to context to be reliable | (three separate commands) — never `<base-branch>` — because
- script | already a status check: `git status --porcelain` empty before step; one-line assertion in the loop | The status must be empty;
- script | before running a candidate, read each `depends_on` ledger row and `git merge-base --is-ancestor` its merge commit (shares with next two rows) | `depends_on` must already be merged into `<base-branch>` before it runs
- script | ledger check, same dependency verifier | every candidate in `depends_on` must have ledger `status: merged`
- script | `git merge-base --is-ancestor <merge_commit> HEAD` exit code, same dependency verifier | `git merge-base --is-ancestor <merge_commit> HEAD` must exit 0 after the pull
- judgement | quality of candidate descriptions | **Descriptions must be concrete enough that
- hook | Skill PreToolUse on `cla:lite-pr` could check args, but "interactive" entry is a reading of the description | Never let a candidate enter `/cla:lite-pr`'s interactive
- judgement | whether a PR number came from the ledger is not visible | never a re-derived branch name or an "in-context" PR number
- judgement | what a silent clean looks like is a reading of the review output | Never treat it as silently clean
- script | same merge-gate ledger check as the other blocking-finding rows | and **never merge a candidate carrying an unresolved blocking finding.**
- script | ledger row status validator accepts only the listed set when a step ends | or `failed-review` from step 7), never `open`:
- judgement | an agent action (rebase) in a conflict case; a Bash hook can't tell which PR is `conflicts` without the ledger | Never rebase a `conflicts` PR: it is left open and flagged.
- script | same moved-head ledger comparison | And it never merges a moved head
- script | resume reads the ledger: refuse `review: clean` unless recorded (same resume validator) | Two things a resume never does. It never infers `review: clean`

#### skills/multi-spec/SKILL.md
- script | git_state.py resolves default branch; same as multi-lite | means THIS repo's default branch, resolved — never assumed
- judgement | commit cadence is a sequence property; a post-hoc script could count commits per change but cannot know intended timing | never batch commits to the end.**
- judgement | model turn property | **Never end a turn with nothing in flight.**
- hook | Bash PreToolUse: block `git add -A`/`--all`/`.` (one hook covers every `git add -A` rule) | **Never run `git add -A`.** Path-scope every stage
- judgement | exceptions are a matter of reading | never a special-cased "probably fine."
- script | after push compare `git rev-parse HEAD` with `git ls-remote` SHA; halting is the agent's reaction | Mismatch → halt via `AskUserQuestion`, never silently retry.
- judgement | sequencing of agent calls | awaited sequentially — never parallel.**
- hook | Skill PreToolUse: deny a Skill call whose name is `cla:spec-to-pr` while this skill runs (needs knowing the active skill; approximable) | **This is a proposals-only skill.** Never invoke `Skill(cla:spec-to-pr)`
- judgement | phase ordering; review-then-PR could be seen from `gh pr create` vs review record but needs a run record | (Phase 4) always runs BEFORE the PR opens (Phase 5) — never the reverse
- script | Phase 1 start: check the decisions file exists and is committed (`git ls-files` / `git status`) | Never proceed to Phase 1 from transient conversation state
- judgement | same ordering | this ordering (review-then-PR) is load-bearing, never the reverse.
- judgement | honouring an owner statement | A path the owner states always wins.
- judgement | where the agent reads resume state from | Every phase resumes from git-tracked repo state, never from a log or the plan file

#### skills/multi-spec/references/authoring-brief.md
- judgement | whether a spec honours a floor is content judgement (check_spec_proof checks only the form of stakes) | its floor always applies.
- judgement | whether an authored concern was kept out of the spec is content | raise your concern under `## Open questions`; never change it in the spec.
- judgement | which outcomes matter and word counts is wording | These matter most; never cut one to save words.
- script | check_spec_proof.py could compare design.md decisions to spec text, but agreement is a reading | design.md and the specs must agree; where they would differ, the spec wins
- judgement | what tests ran against is not recorded | Tests and manual checks run on copies or scratch data, never on what the Stakes protect.

#### skills/multi-spec/references/phases.md
- hook | Bash/Write PreToolUse: flag a temp file path (`> <path>`, Write target) inside the repo toplevel; deletion after PR is a step | in the system temp folder, never inside the repo, and delete it after the PR is created.

#### skills/multi-spec/references/plan-schema.md
- enforced | pre-push git hook blocks pushes to the default branch (hooks/git/pre-push); the commit side is not blocked | a Phase-1 commit would land on `<base-branch>`, which this skill may never push
- judgement | source of the done-ness decision | Resume always re-derives "is this change done" from the repository itself
- judgement | same | never from a status field in this plan

#### skills/multi-spec/references/review-gate.md
- judgement | cross-change consistency of obligations needs reading both changes | must be checked against change B's actual `design.md`/`specs/`
- judgement | detecting a binding defect and reporting honestly is judgement | report that, and never record it clean.
- judgement | whether a finding's remedy was reconsidered | A finding never leaves this gate merely because its first remedy was wrong.

#### skills/cla-setup/SKILL.md
- hook | Edit/Write PreToolUse: deny a path inside the installed plugin cache (`CLAUDE_PLUGIN_ROOT` under `~/.claude/plugins/cache`); not inside this repo's own tree, which is legitimately edited (one check covers every "never write in the plugin tree" rule) | arrives with the install and is never touched
- hook | Write PreToolUse: deny the Write tool on an existing file while cla-setup runs (Write already needs a prior Read); the Bash redirect form needs a command regex for `> file` with no `-e` guard, approximate | The never-clobber contract below applies to every step
- hook | Bash PreToolUse: flag a bare `>` redirect to a repo file (not `>>`, not `/dev/null`, not a guarded `if [ -e` form); false positives on ordinary scripting, so approximate | via a guarded idiom, never a bare redirect
- hook | same bare-redirect check | ALWAYS guard with `if [ -e "$f" ]`
- script | check after the run: `notes.md` byte-identical to its pre-run hash; needs a pre-run snapshot | `notes.md` is ALWAYS skipped, even though the seed content differs
- script | after cla-setup, assert no `overlays/*.md` was created that did not exist (git status / directory listing) | **Overlays are optional, and this skill never creates one.**
- judgement | whether the report states the unchecked config honestly is wording | say so, never call the rules current
- script | after cla-setup, assert `CLAUDE.md` and `AGENTS.md` are byte-identical (git diff on those paths) | This skill never touches `CLAUDE.md`
- script | git diff after run: no `*.local.md` machine-read file changed shape | machine-read `*.local.md` files are never reshaped here
- hook | Write PreToolUse: deny Write over an existing path (same hook as never-clobber) | never overwriting a file and never
- hook | Edit/Write PreToolUse: deny a path under the legacy plugin-cache overlay location (same plugin-cache hook) | legacy-location overlay (never edited)
- script | check_no_project_tokens.py already runs against shipped plugin prose (repo-side); for a repo's facts a small token-form check could run in setup | compound repo-specific tokens only, never generic words
- hook | Edit/Write PreToolUse: deny a target path outside the repo or inside the plugin cache (same hook) | **Every target must be repo
- hook | same plugin-cache path hook | recommendation, never written. A declined proposal
- enforced | check_fact_paths.py (cla-setup scripts) exits 0/1/2 on stale fact paths; it is the step's own check | It MUST exit 0. Exit 1 names each stale path
- script | the step's runner could treat exit 2 as failure explicitly; the prose is the only reader of the code today | never read a 2 as a pass
- script | same overlay-creation diff check | Does **NOT** create overlays, and never writes a fact into one.

#### skills/cla-setup/references/economy-rules-block.md
- script | git diff check that CLAUDE.md is untouched (same as SKILL.md row) | ordinary diff; if `.claude/` is ignored it stays local. This skill never touches
- judgement | whether a block failure stopped the other blocks is flow | A failure here never stops the

#### skills/cla-setup/references/facts-file.md
- script | same `*.local.md` unchanged check | **Machine-read `*.local.md` files stay where they are and are never reshaped here:**
- judgement | what the manifest says is read from the repo | read the real manifest, never assume a stack
- script | check_fact_paths.py or a small scan of the facts file for secret-shaped values (key patterns) | (never the secret VALUES — only paths/names)
- enforced | check_spec_proof.py exits 2 on any other form of the stakes heading | so never reword or merge it
- judgement | whether a proposal is offered by default is flow | never proposed by default.
- enforced | check_spec_proof.py exits 2 on a spec-map heading with no bullet | in another form (`### Spec map`). Never write the
- script | check_spec_proof.py already checks the form; "invent a path" could be checked by path existence (check_fact_paths.py) | heading when there is no map, and never invent a path
- script | assert terminology file absent before and after setup unless it existed (git status) | this skill never creates it and only reconciles it

#### skills/cla-setup/references/openspec-rules.md
- script | seed_openspec_rules.py could refuse to write without an explicit confirmation flag and prove the file byte-identical otherwise (git diff) | Never make this edit silently.
- judgement | honest reporting of the unchecked config | say so, and never call the rules current

#### skills/cla-setup/references/overlay-reconcile.md
- judgement | glob choice is a coding style in the step | glob generically — never a hardcoded
- hook | same plugin-cache edit hook | **Legacy-location overlays are never edited.**
- judgement | same token-style choice | only, never generic words that legitimately appear in portable prose

#### skills/cla-setup/references/spec-map-scaffold.md
- judgement | offered vs imposed is an interaction choice | This skill offers a default scaffold and never imposes one.
- hook | Write PreToolUse: deny Write on an existing path (same never-clobber hook) | a path that already exists is never overwritten, so ask for another
- hook | Edit/Write PreToolUse: deny the plugin cache path (same hook) | other path inside the repo, never under the plugin tree

#### skills/review-change/references/checklist.md
- repo-test | test_check_labels_agree.py and consistency tests keep the two reader files (checklist, dispatch) in step; no consumer-side check | Any change to review behavior MUST be made in these two files
- judgement | verifying a claim against source is the reviewer's act | claim in an artifact must be verified against the actual source before accepting it
- judgement | review rubric heading, the reviewer decides coverage | ### High-yield checks (always do — these catch the vast majority of real issues)
- judgement | review rubric heading | ### Weight and proof checks (always do, on both size-gate paths)
- script | the review step already runs check_spec_proof.py; it could fail the step when the exit code is 2 and no `[Open]` line is in the report | so report an `[Open]` line saying so and never write "no breach"
- script | check_spec_proof.py reads marker lines and flags "no test yet" misuse (marker honesty already in its PROBLEM lines) | it never means "no test yet"
- judgement | whether a test harness mirrors the real object needs reading | the harness MUST structurally mirror the real object
- judgement | whether a row carries a verbatim quote vs NOT-FOUND is a reading of evidence | MUST resolve to one of exactly two things
- judgement | path-independence of an answer | because the answer must not depend on which path ran
- script | check_chain_obligation: a script could grep the change dir for each carried obligation id and emit NOT ADDRESSED (consistency test exists only in this repo) | **No match anywhere in the change directory → `NOT ADDRESSED`, always.**
- repo-test | test_chain_obligation_carry.py pins the wording; a verdict/report cross-check in a script is possible but reports are free text | a report carrying one can never be `READY`
- judgement | whether an open question became a finding is a reading | never into a findings section
- repo-test | test_chain_obligation_carry.py; report format is free prose | A report may never pair `NOT ADDRESSED` with `READY`.
- judgement | whether a fix added a proving test is a reading of the diff | the artifact fix MUST add a proving test
- script | for an artifact fix, check the tasks.md diff gained a subtask line (git diff of tasks.md); the test check is a reading | the fix MUST also add (or extend) a `tasks.md` subtask
- judgement | no-sycophancy is an attitude | never facts to accept
- judgement | whether a verdict rests on verifications | A READY verdict must rest on your own grounded verifications
- judgement | what counts as inherited | Inherited obligations and Step 2b are always blocking.
- script | a report linter: a line labelled Critical under a `### Suggestions` heading (regex on the review report text); only if reports have fixed form | never prints under `### Suggestions`
- script | same report linter: label vs section heading match | never edit the label down to match the section

#### skills/review-change/references/dispatch.md
- script | the dispatch step could run the stated grep count and refuse when it does not print 0 | <pr-base>' <file>`; it must print 0
- judgement | whether a brief contains a pointer rather than content | Never leave a bare pointer to a file instead
- hook | PreToolUse on Agent calls for review agents: cannot restrict a subagent's tools beyond the agent definition; Edit/Write by a review agent is checked by the definition's tool list (agent frontmatter `tools`) | > **Read only — never write to the working tree.**
- script | brief-fill check: fail when the dispatched prompt text contains `(none recorded)` for the protected-areas row (Agent PreToolUse hook on prompt text, narrow literal) | never `(none recorded)`
- judgement | lockstep doc update is a reading | and must update the load-bearing spec/doc files for that formula together
- judgement | relabelling is a reading | > An `[Open]` line is NOT a finding and carries no severity. Never relabel one
- hook | same read-only agent-definition check | > **Read only — never write to the working tree.**
- judgement | doc list coverage needs reading | and it must not leave out a document on the repo's doc list
- hook | same read-only agent-definition check | > **Read only — never write to the working tree.**
- judgement | same relabelling | > An `[Open]` line is NOT a finding and carries no severity. Never relabel one

#### skills/project-review/SKILL.md
- judgement | step ordering of the agent | This step MUST complete before Step 2's dispatch

#### skills/project-review/references/review-agents.md
- judgement | whether findings name the app is wording | every finding MUST name the app/package it applies to
- judgement | whether evidence cites path+line is a reading | its evidence MUST cite a specific path + line or grep result

#### skills/annotate/SKILL.md
- repo-test | test_annotate_server.py hashes the document across a render/serve/annotate cycle; no consumer-side check | **The document is never written to.**
- repo-test | test_temp_dir_isolation.py; render_doc.py puts output under tempfile.gettempdir()/cla-annotate (enforced in code for the default path) | goes to a temp directory, never into the repo
- judgement | whether the agent reports an archived change's "no base" honestly | so the text it replaced is gone. Never report
- script | annotate render step already runs render_doc.py; a staleness check (rendered page hash vs document hash) could be built into the serve step | **Always re-render before serving.**
- judgement | reading-aid framing of the coverage view | ### The coverage view is a reading aid, never a verdict
- judgement | how the agent presents unverifiable bullets | Never present these as gaps.
- judgement | grouping in the agent's reply | Its own group, never added to
- judgement | agent's reply wording | **Never restate a coverage row as a defect in the change.**
- judgement | agent's reply wording | The page states the same distinction; the reply must
- script | render_doc.py link generation and test_render_doc.py already check anchors resolve; a render-time check that every link target exists is plausible | **Never let a link be a guess.**
- repo-test | test_annotate_server.py (sha256 of the document across a cycle) | **Never write to the document being annotated**
- enforced | annotate_server.py binds `("127.0.0.1", port)` (line 722) and rejects non-loopback Host/Origin (lines 75, 78) | **Never bind the server to anything but `127.0.0.1`.**
- repo-test | test_temp_dir_isolation.py (render output goes under the system temp dir, so nothing to commit by default) | **Never commit a rendered page.**
- judgement | a delete of the annotations file is an ordinary `rm`/`git rm` Bash command of an unknown path; no script in annotate deletes it | **Never delete, archive or rewrite an annotations file.**
- judgement | whether a resolution is invented is a reading of the agent's act | **Never invent a resolution to tidy the list.**

#### Candidates

##### 1. Block bulk staging in Bash (`git add -A`, `--all`, `.`)
Bash PreToolUse hook in the existing dispatcher; match `git [global opts] add` with `-A`, `--all` or `.` as the pathspec after collapsing quoted spans (the technique `warn-stray-scratch-artifact.py` already uses). Protected area: user's files. Size: small (one function).
- skills/multi-lite/SKILL.md: **Never run `git add -A`.** Same rule as `/cla:lite-pr`
- skills/multi-spec/SKILL.md: **Never run `git add -A`.** Path-scope every stage

##### 2. Deny Edit/Write into the installed plugin cache
Edit/Write PreToolUse hook: deny when the path is inside the plugin's installed cache (`~/.claude/plugins/cache/...`), but not in this repo's own working tree. Protected area: shipped to other repos / user's files. Size: small to medium (dispatch plus a path rule).
- skills/cla-setup/SKILL.md: arrives with the install and is never touched; legacy-location overlay (never edited); **Every target must be repo; recommendation, never written. A declined proposal
- skills/cla-setup/references/overlay-reconcile.md: **Legacy-location overlays are never edited.**
- skills/cla-setup/references/spec-map-scaffold.md: other path inside the repo, never under the plugin tree

##### 3. Chain ledger gate before merge and resume (script at the merge step)
A small stdlib script `chain_gate.py` the multi-lite/multi-pr merge step runs: reads the run ledger row, confirms the PR was opened by this chain, `review: clean` is recorded, no blocking finding is unresolved, the PR head SHA equals the tested head, and every `depends_on` merge commit is an ancestor of HEAD (`git merge-base --is-ancestor`). Exit non-zero blocks the merge. Protected area: user's files (merges). Size: large (needs the ledger schema as input; the ledger already exists).
- skills/multi-pr/references/discover-and-gate.md: The chain never merges a PR it did not open
- skills/multi-lite/SKILL.md: Never merge a candidate carrying an unresolved blocking finding; **Resume never infers clean:**; **Resume never merges a moved head either:**; `head unverifiable (ledger lost)`, never merged
- skills/multi-lite/references/candidate-extraction.md, candidate-loop.md: never merge a candidate with an unresolved blocking finding; A resume never merges a head this run did not test and review; `depends_on` rows; `git merge-base --is-ancestor <merge_commit> HEAD` must exit 0 after the pull; And it never merges a moved head; It never infers `review: clean`
- skills/multi-lite/references/bootstrap-and-tracking.md: A row missing `deferred` can never resume as clean.

##### 4. Post-run diff assertion for cla-setup (script)
A short check at the end of cla-setup: `git diff --name-only` must not include `CLAUDE.md`, `AGENTS.md`, `*.local.md`, `notes.md`, existing overlays or the terminology file; no new `overlays/*.md`. Protected area: user's files. Size: small to medium (one new script, no new state).
- skills/cla-setup/SKILL.md: This skill never touches `CLAUDE.md`; machine-read `*.local.md` files are never reshaped here; `notes.md` is ALWAYS skipped; Overlays are optional ... never creates one
- skills/cla-setup/references/economy-rules-block.md and facts-file.md: the same `CLAUDE.md` and `*.local.md` rows

##### 5. Never-clobber on Write (cla-setup)
Write PreToolUse hook that denies Write onto an existing repo path when cla-setup is the running skill (needs knowing the skill; otherwise it would fire on all ordinary rewrites, so it is the weakest candidate). Protected area: user's files. Size: medium.
- skills/cla-setup/SKILL.md: The never-clobber contract; never overwriting a file and never
- skills/cla-setup/references/spec-map-scaffold.md: a path that already exists is never overwritten

##### 6. Read-only review agents
Verify every review agent definition under `agents/` lists no Edit/Write/Bash-write tool; a conformance check in `plugin-tests/` runs here, a shipped hook cannot see the agent's identity. Protected area: user's files. Size: small. (Held today by agent definitions; the `Read only` line is prose.)
- skills/review-change/references/dispatch.md: > **Read only — never write to the working tree.** (three entries)

##### 7. Push verification and base freshness (script)
After a push, compare `git rev-parse HEAD` with `git ls-remote` for the branch; before a candidate, compare the local base to `origin/<base>` using `git_state.py`. Protected area: safe writes. Size: small.
- skills/multi-spec/SKILL.md: Mismatch → halt via `AskUserQuestion`, never silently retry.
- skills/multi-lite/references/bootstrap-and-tracking.md: Each candidate's `/cla:lite-pr` run must branch off an up-to-date `<base-branch>`.

##### 8. Temp file outside the repo
Bash/Write hook: flag a redirect or Write target inside the repo toplevel for the multi-spec PR body temp file. Protected area: safe writes. Size: small, but narrow (one rule).
- skills/multi-spec/references/phases.md: in the system temp folder, never inside the repo, and delete it after the PR is created.

##### 9. Review report linter
A script run on a review report: a `Critical`-labelled line under `### Suggestions` fails; `NOT ADDRESSED` together with `READY` fails. Only holds if the report format is fixed. Protected area: honesty. Size: medium.
- skills/review-change/references/checklist.md: never prints under `### Suggestions`; never edit the label down to match the section; A report may never pair `NOT ADDRESSED` with `READY`; a report carrying one can never be `READY`; No match anywhere in the change directory → `NOT ADDRESSED`, always.
