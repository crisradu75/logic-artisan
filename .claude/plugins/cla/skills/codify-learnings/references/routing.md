# Routing, the ladder, and the failure prompts

The one reference for `codify-learnings`: where a fix lands, how far a re-offense climbs, whether
the plugin can be edited here, and the prompts that catch failures a skim would miss.

## The ladder

| Rung | What lands there | Reach |
|---|---|---|
| `checklist` | a prompt under "Failure prompts" below | retro time only — no work session reads it |
| `doc` | memory, a `CLAUDE.md`, `cla.io/overlays/<skill>.md`, a `SKILL.md` | every session that loads it; advisory |
| `hook` | a hook, `.claude/settings.json` | every matching tool call; enforced |
| `script` | a script, or build/lint/test config | every run; the failure becomes impossible |

- **A lesson lands where work sessions load it** — `doc` or higher. `checklist` is only for a check
  that can be made at retro time and never mid-session.
- **A new lesson** enters at the lowest rung that would have prevented it, usually `doc`.
- **A re-offense** climbs one rung above the artifact that failed. Restating it louder on the same
  rung is the failure this ladder exists to stop.
- **A re-offending rule a hook can detect** — a command shape, a path pattern, a branch name —
  becomes a hook. Make it block (`exit 2`) when a violation is always wrong; make it warn
  (`exit 0` and a message) when it has legitimate exceptions the hook cannot tell apart.
- **A `doc` rule that re-offends with nothing mechanical to enforce:** narrow the trigger (a
  sharper sibling failure earns its own rule), or graduate its one mechanical sub-case to a hook,
  or move it to a home with better reach (memory ↔ `CLAUDE.md`). Log a move as a lateral, not a
  climb: the lesson has now failed at two artifacts.
- **When a lesson graduates**, delete the lower-rung text it duplicates in the same fix — a prompt
  below, a `CLAUDE.md` line, a memory entry — unless that text covers more than what graduated.

## Which home

- **About this repo** → its `CLAUDE.md`, or `cla.io/overlays/<skill>.md` when it is about how one
  skill runs here. Git, cloud sessions and reviewers see both.
- **About how this user personally likes to work** → memory, and nothing else goes there. Memory
  lives outside the repo, so a repo lesson written there is invisible to everyone but this machine.
- **About the plugin's portable procedure** → the plugin, if it is writable here; otherwise
  `/cla:report-upstream`.

## Is the plugin writable here?

Check; do not assume. The two cases differ in one stable way: a plugin loaded from a working tree
(`--plugin-dir`, the plugin's own source repo) sits **inside** the repo; an installed one is a
read-only, version-keyed cache **outside** it, where an edit fails or is discarded at the next
update — while reporting as applied.

1. Repo root: `git rev-parse --show-toplevel`.
2. Plugin root: the absolute path of this file, or of the skill's `SKILL.md`, cut at
   `.../plugins/cla`.
3. Plugin root inside the repo root → **writable**. Outside, or either path unknown →
   **read-only**.

| Target | Writable | Read-only |
|---|---|---|
| `cla.io/**`, repo `CLAUDE.md`, `.claude/settings*.json`, memory | edit | edit |
| a `SKILL.md`, `references/**`, `hooks/**`, `lib/**`, any plugin script | edit | `/cla:report-upstream` |

Read-only never means dropping the lesson, and never means writing a portable fix into a local
overlay to make it stick: that reaches no other repo and leaves the prose that missed unchanged.
Say in the fix's line that it is going upstream.

## Failure prompts

Prompts for Step 1, not destinations. Each names a failure that is easy to live through without
noticing.

- **Done without proof.** Was a change declared done, or a count or diagnosis stated, without the
  command that shows it — the repo's own build, lint and test commands (`cla.io/project-facts.md`
  or the overlay), a typecheck right after a bulk edit, a clean environment rather than a dev box?
- **Not asked for.** Did you do work the user did not ask for, or carry out a plan other than the
  one you announced?
- **Secondary source first.** Did you reason from a docstring, memory, a summary or a peer repo's
  working tree when one read of the primary source — published docs, the code, `git show
  <branch>:<path>` — would have settled it?
- **Unauthorised action.** Did you delete, force, reset, commit, push, merge or publish without
  the user's authorisation for that artifact? An earlier yes does not carry to later work.
- **Blast radius.** Did a change reach further than you checked — a caller in another directory,
  a sibling copy of the same claim, every place that enumerates the same set?
- **Platform-divergent behaviour.** Did something depend on the OS, shell, stdout encoding, an
  environment default, a path separator or a runtime version? Check the other platforms' failure
  classes too, not only the one you hit.
- **Silent failure.** Did something return a plausible wrong value, swallow an error, take a
  fallback on an unexpected value, or use a sentinel that collides with real data?
- **Wrong distribution.** Did a heuristic, threshold, timeout or retry count fail on real inputs?
- **Guessing at a cause.** Did finding a cause take more than two turns? What signal was missed —
  and would a deterministic loop (`/cla:diagnose`) have found it sooner?
- **Pushback.** Did the user push back with a question, repeat a correction, or remind you of a
  documented rule? A question like "why would X matter?" means your model is wrong: rebuild it,
  do not defend it. A repeated reminder means the rule is not load-bearing: escalate it.
- **Asked or assumed wrongly.** Did you ask something the files already answered, or silently
  decide something only the user could — an ambiguous mapping, category or default?
- **Unchecked agent.** Did you act on a sub-agent's finding without checking it against the code,
  or brief an agent with a paraphrase instead of the artifact itself?
- **Friction.** Were tool calls denied, or the same permission prompted repeatedly? Did a hook
  fire when it should not have, or stay silent when it should have fired?
- **Doc drift.** Did a change leave a doc, a `SKILL.md`, a table, a count or a path describing the
  old behaviour? Grep for the old name before calling it done.
- **Not written down.** Did the user explain something, or did you find something by grepping,
  that belongs in `CLAUDE.md` or a `SKILL.md`? Did the user state a working preference you will
  need again (memory)?
