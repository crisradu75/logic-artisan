# Orchestration cost rules

Cost rules for an orchestrator that dispatches agents and runs tests. Tokens are money, so each
rule below saves some without dropping quality.

1. **Name the model on every dispatch.** Every `Agent` call passes an explicit `model:`. A forgotten
   one silently inherits the session model. Choose the model by the task.
2. **Write a complete first brief.** Put every known item and every standing rule in it. Ask for a
   report of about 300 words. A finding added after review costs a full build-and-review cycle.
3. **Test narrowly, then once, sized to the change.** While iterating, run only the touched test
   files. Run one final verification on the final commit. The orchestrator re-verifies that
   commit itself, at the same size, before it offers a merge. Size the run on the whole diff:
   - Use the targeted gates only when every changed file is docs, config or infra-as-code.
     Config and infra-as-code qualify only when neither the build nor the test suite loads them.
     The targeted gates are lint and typecheck where the repo has them, plus the tests and checks
     that read the changed files.
   - Any other diff gets the full suite once. When unsure, treat the change as code.
   - A verification policy in the repo's instruction file (`CLAUDE.md` or `AGENTS.md`) or in
     `cla.io/project-facts.md` replaces the two bullets above.
   - A skill whose merge gate names the full suite or the full gate keeps it for that merge. Apply
     that gate as the skill words it, including any skip the skill states. A repo policy may add
     to that gate but never shrink it.
4. **One PR at a time per area.** Different areas can run in parallel. Two PRs in one area cause
   rebases and version-bump clashes.
5. **Hand off a long chat.** When the orchestrating chat grows long, write a handoff file and
   continue in a fresh session instead of carrying the old context.
6. **Put high-risk implementers on Opus.** A task is high risk when it shows one of the risk signals
   in the review-sizing rules. Other implementers use Sonnet.
7. **Check for debris when you run the tests.** Before the final test run, save the output of
   `git status --porcelain --ignored --untracked-files=all` outside the repo, in a scratch or temp
   directory. Run it again after, and diff the two. Any new line is debris, so report it. Ignored
   caches and virtualenvs that were already present show in both lists and cancel out. Ignore interpreter
   caches (`__pycache__/*.pyc`) in the diff only for `__pycache__` folders beside tracked `.py` files, and delete the half-written `*.pyc.<digits>` files under `__pycache__/` that
   parallel workers leave. A missing before snapshot means the check did not run, so warn.
8. **Give each parallel agent its own scratch folder.** Use `scratchpad/<change-name>/` and name it in
   the brief. Agents that share a folder overwrite each other's files, such as a PR body. Keep
   `scratchpad/` in the repo's `.gitignore`. Rule 7's check lists ignored files one by one, and an
   empty folder not at all, so the files agents write there show as new lines in the after list:
   leave the lines under `scratchpad/` out of rule 7's diff.
9. **Give each parallel agent its own copy of a shared test environment.** Examples are a database
   or a port. Never make agents queue on a lock, because it serialises them. Remove the copies when
   the agents finish.
10. **Run full test suites one at a time across parallel agents.** Rule 3 sets the scope for each
    agent: its own area while iterating. Never let two full suites run together. After the merges,
    the orchestrator verifies the base branch once. Rule 3 sizes that run over every merged diff:
    the full suite if any merged diff falls outside the targeted case.
11. **Plan the merge order up front, and merge one PR at a time.** Only the last PR in the order
    edits a file that several areas share. Earlier PRs list the lines they need in their body.
    The last PR applies them, so no merge leaves the next PR conflicting.
12. **Check GitHub for PR state.** Do not wait on an agent's report to learn whether a PR is open,
    green or merged. Run `gh pr view` on the PR for open or merged, and `gh pr checks` for green,
    because an agent's report can be stale.
13. **Plan for an agent that cannot push.** A guard hook or a deleted shared file can block it.
    The agent reports and stops. The orchestrator then pushes the branch and opens the PR.
14. **Read-only agents may run beside the base-branch verification.** An agent that only reads, such
    as a review or an analysis, can run while the orchestrator's single verification of the base
    branch (rule 10) is live. Read-only means it writes nothing to the checkout; files in its own
    scratch folder (rule 8) are allowed, because rule 7's diff leaves them out. An agent that edits
    the checkout, runs tests, or shares the test database (unless it has its own copy, rule 9)
    waits for the verification to end. Rule 10 still holds:
    one full suite at a time.
