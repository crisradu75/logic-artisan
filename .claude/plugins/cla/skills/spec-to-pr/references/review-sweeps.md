# Review — sweeps and applying a round's fixes

Read from the Review stub in `SKILL.md`: the doc-staleness sweeps run in every Review pass whose proposal retires something; "Applying a round's fixes" is read before the first fix of a FIX FIRST / RETHINK round. Review behaviour itself lives in `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` (agent prompts: `dispatch.md` beside it); edit it there, never here or in the orchestrator.

## Doc-staleness sweeps

**Application sweep.** When the proposal touches application source, list every word or symbol it retires (deleted functions, removed props, replaced modules, renamed domain keys, retired constants) and dispatch `doc-sweeper` (haiku, read-only — `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`) with that list PLUS this repo's doc-path list from `cla.io/project-facts.md` ("Doc-sweep paths (five-path list)"; `cla.io/overlays/spec-to-pr.md` when that file is absent). `doc-sweeper` knows no doc paths of its own; the caller supplies them all.

**`.claude/`-meta sweep, in the SAME Review pass.** When the proposal touches a `${CLAUDE_PLUGIN_ROOT}/skills/<name>/SKILL.md` or `references/*.md`, list every mechanism or rule it retires or alters (a dispatch mechanism, a demotion policy, a tool dependency) and dispatch `doc-sweeper` again over `${CLAUDE_PLUGIN_ROOT}/skills/<name>/SKILL.md` and `${CLAUDE_PLUGIN_ROOT}/skills/<name>/references/*.md`. The application sweep cannot see these.

**Reading what comes back** — a `path:line — symbol` hit list and a mandatory `Scanned: N files` footer:
- **Check the footer first.** `Scanned: 0` for any supplied surface, or a non-empty `Unresolved` list, means it searched less than you asked: fix the path list and re-dispatch.
- **A non-zero footer does not make a zero-hit result true.** Re-run the search yourself for every zero-count symbol — the whole result or one symbol's line — as one alternation over each supplied path or glob in turn (one search per entry; never widen to a repo-wide pattern). Any hit means the sweep under-searched: add the hits, plus one Handoff Issue naming the miss.
- **Every hit is an Important Review finding.**

**Large change.** Checks 0a–0h default to a `fact-gatherer` dispatch returning the context-brief rows as a pass/fail table (the checklist's "Cost offload for large changes"); you adjudicate every ✗ row. Both helpers return schema'd output, not prose.

## Applying a round's fixes

1. **Capture the rejected-alternatives snapshot BEFORE the round's first fix.** Read the change's `design.md` rejected-alternatives / explicitly-rejected-decisions section and hold it for the round. The fixes routinely edit `design.md` itself, so a later read sees the edited file.
2. **Apply** each Critical and Important finding by Edit/Write under `openspec/changes/<name>/`: to design.md or tasks.md, and to spec text only when the finding is about an outcome or interface. For prose, prefer this repo's canonical terms from `cla.io/terminology.md` when it exists and covers the concept.
3. **Re-validate each fix landed** — not a re-dispatch: grep the artifact for the symbol, heading or clause the finding named, or re-read the section. Still visible → a follow-up edit in the same round.
4. **Check every applied remedy against the snapshot.** Each fix on this path is one the orchestrator both specified and judges, so confirm none reintroduces a rejected alternative. Never `git show HEAD:<path>`: Review runs before Ship, so a fresh change dir is not committed yet and the git form fails.
   - **No snapshot captured → the check has not run.** Review `warn`, recorded under *Issues encountered* as `rejected-alternatives check did not run (no snapshot captured)`, the round's remedies treated as unchecked.
   - **No `design.md`** → out of scope, not a breach.
   - **A hit is a Critical on the fix itself.** Withdraw or re-specify the remedy; it does not stand on having resolved the original finding. Where the *rejection* now looks wrong, amend `design.md` explicitly — "the fix brief said so" is not an amendment.
5. **Marking.** Every remedy on this path is orchestrator-specified, so state that once for the phase in the Handoff report rather than marking each; per-remedy `remedy: orchestrator-specified` belongs to Revise. **This control is weaker than an independent reader and raises no round cap** — say so rather than implying parity.
