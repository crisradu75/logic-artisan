# reviewer-agents: live check of the model override (tasks 1.1 and 3.7)

Source: PR "feat: reviewer-agents", merged as `0c8e10f`. Archived at
`openspec/changes/archive/2026-10-12-reviewer-agents/tasks.md`, where 1.1 and 3.7 are unticked.

Run this in a FRESH Claude Code session started with `./cla`. The three new agents
(`cla:code-reviewer`, `cla:comment-analyzer`, `cla:silent-failure-hunter`) register only at session start.

## What is unknown

1. Does a `Workflow` `agent()` call that passes `model: "opus"` override the model in the agent file
   (`code-reviewer.md` is `sonnet`)? Only the Agent tool schema's own wording says so; nobody ran it.
   The high-risk review row relies on it (`model-routing.md`, Routing table).
2. Does a reviewer with only Read, Grep and Glob read the change from a diff file the caller saved outside
   the working tree? (`revise.md` round 1 and round N, `lite-pr/SKILL.md` Review, `subagent-brief.md` slots 3 and 4.)
   Also settle whether a Git Bash `mktemp` path (`/tmp/...`) is readable by `Read` on Windows, or the
   scratchpad must be used.

## The check

- Save a small diff to the session scratchpad. Dispatch `cla:code-reviewer` three ways on it: via `Workflow`
  `agent()` with `model: "opus"`, via `Workflow` `agent()` with no `model`, and via the `Agent` tool with
  `model: "opus"`. Each brief names the diff file path.
- Read the model each ran on from its transcript: `python3 plugin-tests/scripts/meter.py <transcript folder>`
  prints messages per model. Quote cost only from that script.
- Delete the diff file afterwards. Leave no debris.

## What to change from the result

- Override works in both paths: tick 1.1 and 3.7 in a one-line `docs:` PR to the archived tasks, and
  say so in `model-routing.md`.
- Override fails in `Workflow` only: the high-risk row must use the `Agent` tool, or ship a second
  Opus file; ask the user which (the user chose "one file, Opus per call" earlier on the assumption it works).
- A reviewer cannot read the diff file: fix `revise.md:37` and `:69` (`$DIFF_FILE` is undefined only at `:69`) and the
  `mktemp` wording, in `revise.md` and `lite-pr/SKILL.md:144`. (`subagent-brief.md:121` never mentions `mktemp`;
  it only says "outside the working tree".)

Suggested path: `/cla:lite-pr` for the doc change, `/cla:spec-to-pr` only if the Opus file has to be added.

## Outcome (2026-10-13)

Three dispatches of `cla:code-reviewer` (file says `model: sonnet`) on a diff file in the session scratchpad,
models read with `python plugin-tests/scripts/meter.py <transcript>`:

- `Workflow` `agent()` with `model: "opus"`: claude-opus-5-5 only (6 messages).
- `Workflow` `agent()` with no model (control): claude-sonnet-5-5 only (2 messages).
- `Agent` tool with `model: "opus"`: claude-opus-5-5 only (5 messages).

So the override works in both paths, and 1.1 and 3.7 are ticked. All three reviewers (Read, Grep, Glob only) read
the scratchpad diff file. All three got "File does not exist." from `Read` on the Git Bash `mktemp` path
`/tmp/tmp.YpojiMYNVX`, so on Windows a `/tmp/...` path cannot be handed to a shell-less reviewer. `cygpath -w`
converts it to a Windows path, but that was not tested with `Read`. The docs now name the session scratchpad.
