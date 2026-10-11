# orchestration economy (shared by the chain skills)

Cost rules for an orchestrator that dispatches agents and runs tests. `multi-lite`, `multi-pr` and
`multi-spec` cite this file from their "run thin" rule. Tokens are money, so each rule below saves
some without dropping quality.

1. **Name the model on every dispatch.** Every `Agent` call passes an explicit `model:`. A forgotten
   one silently inherits the session model. Choose per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`.
2. **Write a complete first brief.** Put every known item and every standing rule in it. Ask for a
   report of about 300 words. A finding added after review costs a full build-and-review cycle.
3. **Test narrowly, then once.** While iterating, run only the touched test files. Run the full
   suite once, on the final commit. The orchestrator re-verifies that commit itself before it offers a merge.
4. **One PR at a time per area.** Different areas can run in parallel. Two PRs in one area cause
   rebases and version-bump clashes.
5. **Hand off a long chat.** When the orchestrating chat grows long, write a handoff file and
   continue in a fresh session instead of carrying the old context.
6. **Put high-risk implementers on Opus.** A task is high risk when it shows a signal from "Review
   sizing by risk" in `model-routing.md`: writes or deletes of data, money or scoring, auth,
   guard hooks, concurrency, or changes to agent instructions. Other implementers use Sonnet.
7. **Check for debris in the Test phase.** Before the final test run, save the output of
   `git status --porcelain --ignored --untracked-files=all`. Run it again after, and diff the two.
   Any new line is debris, so report it. Ignored caches and virtualenvs that were already present
   show in both lists and cancel out.
