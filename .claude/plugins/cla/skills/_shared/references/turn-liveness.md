# turn-liveness — how a turn of an unattended chain ends

Read by the chain orchestrators (`multi-pr`, `multi-lite`, `multi-spec`; `spec-to-pr` states the same
rule for its phases). Each keeps a one-sentence rule in its `SKILL.md` and restates it at the seam
between two units, where its reference file has been closed.

## The failure

The rule against pausing to ask "ready to continue?" forbids *asking permission*. The failure that
actually stops a chain asks nothing: the orchestrator announces the next unit, ends the turn believing
it is continuing, and nothing re-invokes the session. The chain does not pause, it stops, silently,
until a human notices. The seam between two units is where it happens: a finished unit with a status
line reads as a natural place to stop.

## The test

The question is not "did I ask the user something" but **is there a pending event that will re-invoke
this session?**

- A backgrounded `Agent` or `Bash(run_in_background: true)` is safe: its completion notification
  wakes the session.
- A tool call in the same turn is safe: it does not end the turn at all. The next
  `Skill(...)` or awaited `Agent(...)` call of the loop is one.
- An idle turn has no wake signal.

## The mechanical form

Status text and the next tool call go in the **same message**. If there is no tool call to pair the
text with, the unit is not over: start the next one instead of narrating the last. "Is there a tool
call in this message?" needs no judgement, and the judgement version ("does this read like an
ending?") is the one that failed in practice.

## The two cases

Ending a turn is legitimate in exactly two cases: a backgrounded dispatch is genuinely in flight, or
the run is complete. Announcing the next step is not a mechanism. A blocker is not a third case: it
goes out as an `AskUserQuestion`, which is itself a tool call, or (where the skill quarantines) the
unit is quarantined and the loop continues with the independents.

## A watchdog, when a seam has nothing to dispatch

Arm one before ending the message, and re-arm it whenever it fires while work remains:

```
Bash(command: "python3 -c \"import time; time.sleep(1500)\"", run_in_background: true)
```

Spell it with `python3`: `sleep` matches no pattern in
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/required-permissions.json`, so it would prompt, which
is the stall the watchdog exists to prevent.
