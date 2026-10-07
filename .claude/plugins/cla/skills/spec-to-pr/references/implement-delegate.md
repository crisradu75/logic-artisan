# Implement — packaging pre-check and the delegate

## Python packaging gotcha

1. **Pre-check (Python packaging gotcha).** Scan `tasks.md` for subtasks that promote a `.py` file to a package (e.g. "add `<name>/__init__.py`" or "rewrite imports as `from .X import Y`"). If any subtask renames or splits a module that has a sibling file with the same stem (e.g. `tests/fixtures.py` AND `tests/fixtures/` both exist or would coexist), flag it: `python3 -m <pkg>.<sibling>` will silently resolve to the file, not the directory. Resolve by collapsing the file into `<sibling>/__init__.py` before the package promotion. Capture the resolution as a one-line note for the Handoff report.

## Delegating Implement to one coding agent

**Delegate-to-subagent escape hatch (context economy on a big change).** For a large multi-file implementation, dispatch ONE coding `Agent` at `model: sonnet` (per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`) to do the edits + tests. **Sized trigger:** delegate when `tasks.md` has **> ~15 subtasks OR the change touches > ~8 files**; below that, implement inline (a delegation brief costs more than it saves on a small change). Judgment, not a hard cutoff.

Structure the brief per `references/subagent-brief.md` (scope / task / do-not-touch / report / done-when) — this delegate is where that file's "done when" slot came from. Its **do-not-touch** slot is the one this site has historically left implicit: name the paths the orchestrator is holding and any a sibling dispatch owns, since scope alone doesn't say what is *someone else's*.

Seven rules make the delegation safe — three about the brief, four about reading what comes back:
- **Full-task enumeration.** The brief MUST enumerate **every** task in `tasks.md` (or explicitly mark the ones you're deferring) — an agent implements exactly what the brief lists and will NOT invent an omitted task, so a task left out of the brief silently stays undone.
- **Trimmed brief.** Inline `tasks.md` plus ONLY the `design.md` sections the tasks actually reference (none, when the change has no design.md) — not the full proposal/design/spec. The agent needs the task list and the design decisions those tasks implement, nothing more; a full-artifact dump is wasted input tokens.
- **Evidence-based terminal contract.** Instruct the agent to end with an explicit `done` or `blocked` status. `done` is valid ONLY when accompanied by hard evidence: the test-run summary line (e.g. `npm run test` output, or the relevant suite's pass count) and the ticked-task count (`- [x]` count vs total). A return that claims done without that evidence is treated as **not done** — do not trust it.
- **A return carrying no status token is `blocked`, never `done`.** One question, not two: does the return carry `done`, `blocked` or `remedy-rejected`? Absence of the token is the whole signal. Do NOT also test for evidence here — a `remedy-rejected` return arrives without work evidence by design, and the reference states why. Full rule, its scope, and the brief wording that goes with it: `references/subagent-brief.md`, "A gate that outlives your turn". The stall shape it catches: a delegate backgrounds a long gate, ends its turn, and returns a standing-by message that reads exactly like a finish.
- **On a miss, settle the tree BEFORE doing anything else — including re-dispatching.** A re-dispatch is a second *writing* agent in that checkout, so it is the more dangerous move, not the safe one. The quiet check gates both it and take-over:

  ```
  git status --porcelain          # what the stalled dispatch left
  git log --oneline -1            # did it commit
  ```

  Plus a process check for a gate that may still be running: `ps` on POSIX, `tasklist` on Windows. **You cannot attribute a process to your delegate** — no attribution comes back — so read this as "is a build or suite running at all", and if one is, wait for it rather than deciding whose it is.
- **Then pick by what the miss was, because one recovery does not fit both.** A `blocked` naming a gate too long for one foreground call will hit the identical wall on a re-dispatch: **run that gate yourself** — the orchestrator may legitimately background it — and carry on from its result. Only a miss with work genuinely unfinished earns a re-dispatch, and that brief is scoped to what remains: re-derive state from `tasks.md` and the tree first, since the stalled delegate's edits are still there and a full re-enumeration would redo landed work.
- **Take-over before the quiet check is not permitted.** It is what produced the recorded ~40-minute incident, where the orchestrator's own commands manufactured the failures it then investigated as a regression. The orchestrator-vs-own-delegate rule above says why; this is that rule at the moment it is most tempting to break.

After the agent returns, run the Post-check task-box count **regardless of what the agent reported** and finish any task it skipped. The post-check is the deterministic backstop; the terminal contract just catches a hallucinated-completion one phase earlier.

**Contract firings leave a trace.** When the contract fires — the delegate claimed `done` without evidence, OR returned no status at all, OR the post-check finds unfinished tasks after a `done` — recovering inline is correct, but the event MUST be recorded as a Handoff Issue (e.g. `Implement delegate claimed done without evidence; 3 tasks finished inline`). Silently absorbing it would mask exactly the delegation-reliability signal the routing telemetry exists to collect. On a `blocked` return: finish the remaining tasks inline (or resolve the blocker and re-dispatch once), and record the blocker as a Handoff Issue either way.
