## Why

A dispatched agent and the orchestrator that dispatched it share one checkout and one clock, and
nothing in the plugin says so. Three filed issues are three consequences of that single omission:

- **#113 — a stop looks exactly like a finish.** A delegate that starts a ~300-second gate in the
  background and then ends its turn produces a return. The harness delivers that return as a
  completion, and the orchestrator reads it as one. Observed four times in a single chain; two of the
  four returned the same sentence, a statement that the delegate was standing by for a completion
  notification that could never reach it, because its turn ending *was* its return. The brief's
  terminal contract (`subagent-brief.md` §5) says what `done` requires and is silent on what a return
  carrying no evidence at all is — so the orchestrator supplies the missing classification by reading
  the prose, and the prose reads finished.
- **#115 — the natural next move manufactures the failure it then investigates.** Believing the
  delegate finished, the orchestrator took over the tree: it ran the correctness gate, `git checkout`
  and `git commit` in the same checkout while its own delegate's work was still live. The failures
  that produced were then investigated as a possible real regression. ~40 minutes. The plugin's
  "Concurrent runs" section (`spec-to-pr/SKILL.md:159`, `references/concurrent-runs.md`, 21 lines)
  covers two *sessions* sharing a clone and says nothing about an orchestrator and its own delegate —
  which is the same hazard with the same cause and no worktree between them.
- **#125 — the honest answer was ad-hoc.** There is no standard brief language legitimising "stop
  rather than invent data". The one run that got it right got it right because the orchestrator typed
  that sentence into that task's brief by hand. Every brief that did not carry it left a delegate
  facing a contract demanding a test-run summary line it could not produce, with returning something
  plausible as the path of least resistance.

The common shape: **the brief's terminal contract defines success and leaves failure to inference.**
A contract that says what `done` requires, and nothing about what an evidence-free return *is*, hands
the classification to whichever party is worst placed to make it.

## What Changes

Four rules, sitting inside the terminal-status vocabulary the sibling change
`fix-brief-binding-defect` establishes (`done` / `blocked` / `remedy-rejected`). **No fifth status is
added and no slot is renumbered.**

- **A return with no evidence block is `blocked`, never `done`.** The orchestrator applies a scan, not
  a judgement: does the return carry a status token from the closed set, and every evidence field the
  brief's slot 5 named? A miss is `blocked` whatever the prose says — including a return that reads as
  finished or announces that it is waiting on something.
- **Long gates run synchronously, and the rule keys on the runner, not on the duration.** A dispatched
  agent runs every gate in the foreground and does not end its turn while a command it started is
  running, because its turn ending is its return and no notification can reach it afterwards. The
  orchestrator's own backgrounding is unchanged — a notification *does* re-invoke a session. A gate
  that cannot finish inside one foreground call is not delegated at all: the delegate returns
  `blocked` naming it rather than backgrounding it.
- **One checkout has one writer at a time**, stated in both directions. Brief-side, slot 3's existing
  forbidden-verb block gains `commit`, `push` and `reset`, plus a prohibition on killing processes and
  deleting build/cache directories the agent did not create. Orchestrator-side — which no brief can
  reach, because a brief travels only to the delegate — the "Concurrent runs" section grows a second
  case: while a dispatch has not returned, or a command started under it may still be running, the
  orchestrator runs no state-changing git command and no gate in that checkout. And the rule that
  would have ended #115 in one line: **a failure observed in a checkout the orchestrator disturbed
  while a delegate was live is not evidence of a regression** and is re-derived from a quiet tree
  before being investigated as one.
- **"Stop rather than invent data" becomes standard brief language**, attached to the evidence
  requirement that creates the pressure. Every value the contract asks for is one the agent produced;
  a value it could not produce makes the return `blocked` with the field named, and a value it
  constructed, estimated or inferred is a reportable defect.

Also: on a miss, the orchestrator's default move is **re-dispatch once**, not take-over, and any
take-over is gated on a read-only check that nothing the previous dispatch started is still running.
A rule that said "take over" without that gate would re-specify #115.

## What already landed, and what that leaves

**PR #163 (merged 2026-08-26, after this proposal was written) shipped part of rules three and four
directly, as prose, closing #115 and #125.** It touched no spec, so the live specification still
carries no requirement for that behaviour. This change therefore does two things now: it
**ratifies** what landed as requirements, and it **implements** what did not.

Measured against the tree 2026-08-27, not against #163's description of itself:

| | state |
|---|---|
| Orchestrator-facing prohibition, plus the not-a-regression half | **landed** — `concurrent-runs.md` §"The orchestrator vs. its own live delegate" |
| `SKILL.md` §Concurrent runs stub and its References-list line | **landed** |
| "Stop rather than invent data", adjacent to the evidence requirement | **landed** — `subagent-brief.md` §"When the evidence cannot honestly be produced" |
| Agent-facing enumeration: `commit`, `push`, process-kill, build/cache directory | **not landed** — slot 3 reads `checkout, switch, stash, branch, worktree add, checkout --, restore, reset`. `reset` is present; the rest are not |
| The two-cases retitle, and the one-invariant rationale | **not landed** — the H1 still reads "worktree per session (full recipe)" |
| Everything under #113 — foreground gates, evidence classification, the on-a-miss ladder | **not landed** |

**The agent-facing gap is the one that reads as closed and is not.** #163 added `commit` and `push`
to the **orchestrator's** rule, where they are plainly visible; the brief's own list, which binds the
other party, was left as it was. An implementer trusting the issue titles — #115 closed, #113 open —
would conclude rule three is done. It is half done, in the half a brief reaches.

**Both closed issues stay cited.** The remaining work is the rest of one design, not a new one, and
dropping #115 and #125 would leave rules one and two standing on nothing.

## Capabilities

### New Capabilities

(none — this change adds requirements to the existing capability below.)

### Modified Capabilities

- `cla-plugin`: four ADDED requirements — a dispatched agent's turn-liveness and foreground-gate
  obligation, the evidence-first classification of a return, single-writer discipline for one
  checkout in both directions, and the standard no-invented-values clause. **No existing requirement's
  text changes**, including `Unattended-run turn liveness`, whose two legitimate turn-endings this
  change narrows *for a dispatched agent* by naming an actor that requirement does not cover, rather
  than adding a third case to it.

## Impact

Prose-only, in three shipped files, all inside `spec-to-pr`. Measured 2026-08-25 with
`wc -l`, `grep -rn 'subagent-brief\|concurrent-runs' .claude/plugins/cla/` and
`grep -n '^## \|^### ' .claude/plugins/cla/skills/spec-to-pr/SKILL.md`:

| File | lines | where the edit lands |
|---|---|---|
| `.claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md` | 115 | §3 (line 45) forbidden-verb block; §5 (line 78) terminal contract |
| `.claude/plugins/cla/skills/spec-to-pr/references/concurrent-runs.md` | 21 | a second case beside the worktree-per-session recipe |
| `.claude/plugins/cla/skills/spec-to-pr/SKILL.md` | 431 | §Concurrent runs stub (line 159), Implement's delegation contract (line 234), the References list (line 415) |

**Blast radius checked.** `grep -rn 'subagent-brief' .claude/plugins/cla/` returns two citing sites —
`spec-to-pr/SKILL.md:234` and `lite-pr/SKILL.md:141` — both citing the brief by its five slot names
(`scope / task / do-not-touch / report / done-when`). This change renames no slot, so both stay
correct. `grep -rn 'concurrent-runs' .claude/plugins/cla/` returns two, both in
`spec-to-pr/SKILL.md` (lines 162 and 415) and both by path; the reference file's title and the
SKILL.md section heading both currently say "worktree-per-session", which stops being the whole story
and is retitled in the same edit.

**Overlap with the sibling change in this batch.** `fix-brief-binding-defect` edits
`subagent-brief.md` §2 and §5; this change edits §3 and §5. The §5 overlap is real and deliberate:
that change adds a fix-brief terminal-contract *block*, this change adds classification and liveness
rules that apply to **every** contract block in the slot, including that one. It runs second, per the
decisions doc's sequencing note, and composes with what that change leaves rather than replacing it.

No script changes, no hook changes, no new agent type. This is synced core, so every added line must
stay portable: no repo token, no dev-tree path, no absolute developer path, and no naming of the
consuming repo's gate command.
