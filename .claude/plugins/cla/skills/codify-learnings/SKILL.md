---
name: codify-learnings
description: "Review the whole current session for failures, check each against the rules earlier runs wrote, propose up to three fixes (tools and hooks before docs) to apply with one prompt, and log the fixes and re-offenses to cla.io/. Run with /cla:codify-learnings."
argument-hint: "[focus-note]"
# Slash-command only (an end-of-session retro the user starts): keeps this description out of the
# always-loaded skill listing. Nothing invokes it programmatically.
disable-model-invocation: true
---

# Codify learnings

Turn this session's failures into at most three fixes that change how the next session behaves.
A rule that already existed and failed again is the most important thing this skill can find.

Before Step 1, read `references/routing.md` — the ladder, where each kind of lesson lives, the
plugin-writability check, and the failure prompts — and `cla.io/overlays/codify-learnings.md` if
it exists, for this repo's memory location and verification commands. `$ARGUMENTS`, if set,
narrows the focus; the review still covers the whole session.

## Step 1 — List the session's failures

Review the **whole session from its first message**, not its tail: a lesson set up early is often
paid for late. List every:

- user correction or pushback;
- reverted edit or abandoned approach;
- denied tool call or permission prompt;
- wasted turn — a re-diagnosis, a question already answered, a detour a tool could have avoided.

Run the failure prompts in the reference over the session to catch the ones you lived through
without noticing. Write each failure as one line with a short quote of what was said or done. No
failures: say so, and go to Step 5 with empty lists.

## Step 2 — Check each against existing rules

For each failure, search for a rule that should have prevented it: every `CLAUDE.md`,
`cla.io/overlays/`, the hooks in `${CLAUDE_PLUGIN_ROOT}/hooks/` and `.claude/settings*.json`, the
memory index (skip it if the overlay does not say where it is and you cannot find it), and the
lessons log. Grep with the failure's keywords — never read the log whole:

```bash
grep -n -i '<keyword>' cla.io/lessons-learned/lessons-learned.md
```

- **A hit is a re-offense**: the rule existed and did not hold. Key it by that artifact's path or
  hook name (`CLAUDE.md`, `hooks/block-cd-in-bash.py`), never by a slug you made up; a hit in the
  lessons log points at where an earlier fix landed, and that artifact is the key. Its fix goes
  **one rung above** that artifact (reference, "The ladder").
- **No hit is a new lesson**: it enters at the lowest rung that would have prevented it.

## Step 3 — Propose at most three fixes

- **Each fix cites the failure it answers, quoted.** A candidate with no session failure behind it
  is dropped — not deferred, softened or folded into another. Rank by payoff and cut after the
  third, memory included; one real lesson means one fix.
- **Prefer fixes over diagnostics.** When the failure was "I had to diagnose X by hand", the first
  fix makes the tool handle X — a script, a config, a hook, a smoke test — and a doc or memory note
  is at most a second aid. Ask: could a config or script change have prevented the detour?
- **Route by writability** (reference, "Is the plugin writable here?"). Read-only: a fix to a
  plugin file goes to `/cla:report-upstream`, and its line says so.
- **Pick the home** (reference, "Which home"): repo lessons go to the repo's `CLAUDE.md` or
  `cla.io/overlays/`; memory holds only how this user personally likes to work.
- **When a fix graduates a lesson**, the same fix deletes the lower-rung text it duplicates.
- **Never propose edits to** a skill's bundled scripts (`**/scripts/**/*.py`), `openspec/**`, or a
  vendored framework directory. The repo's own tooling, configs and source are in scope.

Show only the numbered list, most valuable first:

```
**1. <imperative title>** (`<target path>`, <rung>) — <the fix, one line>.
   Failure: "<quote>". Re-offense of `<artifact>`, escalated to <rung>.
   Benefit: <what this saves next time, in plain words>.
```

Drop the re-offense clause for a new lesson. A fix going upstream names `/cla:report-upstream` as
its target.

## Step 4 — One prompt, then apply

```
N fixes proposed. Apply which? (y = all / n = none / indices, e.g. 1,3)
```

- Indices apply those and mark the rest REJECTED; `y` applies all; `n` rejects all.
- **Empty input is not consent.** Ask once more; a second empty answer is `n`.
- Rejection is an ordinary outcome. Never argue a rejected fix back onto the list.
- Nothing is written before this answer — memory included.

Apply each accepted fix with the tool it needs; for one going upstream, invoke
`/cla:report-upstream` with the fix and the failure it answers.

## Step 5 — Log

**Lessons log.** Prepend one entry of at most 150 words to `cla.io/lessons-learned/lessons-learned.md`,
directly under its title (create the file with a `# Lessons learned` title if it is missing; read
only its first lines). Newest first, entries separated by `---`:

```
## <YYYY-MM-DD> — codify-learnings
- APPLIED 1. <title> (`<target>`, <rung>)
- REJECTED 2. <title>
- Re-offense: `<artifact>` → <rung>
```

**Ledger.** Append one record:

```bash
echo '<record-json>' | python3 ${CLAUDE_PLUGIN_ROOT}/lib/log_run.py codify-runs.jsonl
```

Build it from this example, which the writer accepts as written:

```json
{"ts": "2026-10-08",
 "applied": [{"target": "hooks/block-cd-in-bash.py", "rung": "hook"}],
 "re_offenses": [{"artifact": "CLAUDE.md", "escalated_to": "hook"}]}
```

- `ts` is today's date. `applied` has one entry per APPLIED fix: its target path
  (`report-upstream` for one filed upstream) and its rung. `re_offenses` has one entry per
  re-offense found in Step 2: the failing artifact's path or hook name, and the rung its fix
  proposed. Either list may be empty.
- A rung is one of `checklist`, `doc`, `hook`, `script`.
- `log_run.py` refuses an off-shape record with one line naming every field that is off. Rebuild
  the record from the example, fixing each named field, and pipe it again **once**. A second
  refusal, or any other failure: say the line was not written, and finish — a missing ledger line
  never blocks the run.

The ledger and the log are tracked files; commit them with the applied fixes.

Close with one line: fixes proposed, applied and rejected, and each re-offense with the rung it
went to.
