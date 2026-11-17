# Decision 2026-11-16: recursive self-improvement (the `mnemo-improve` loop)

Topic: how the Mnemo improvement loop changes storage and skills, and whether it may change itself. Made with `/cla:shape-decision` on 2026-11-16. Builds on `cla.io/decisions/plugin-architecture-2026-11-16.md` (Q1 no GitHub checks, Q8 loop left open) and `cla.io/decisions/plugin-structure-2026-11-16.md` (Q1: all five skills ship; `mnemo-improve` is built last).

Grounded in: this repo's `CLAUDE.md`, `.claude/rules/cla-economy.md`, `cla.io/project-facts.md`; the CLA plugin's `skills/report-upstream/SKILL.md` (v2.3.0); and in `crisradu75/research`: `mnemo/build-guide/build-guide-report.md` (section 3, Costs, Risks, Privacy) and `cla.io/decisions/2026-11-15-mnemo-design.md`.

This decision **replaces** parts of the 2026-11-15 design: the "additive only" skill-edit rule, the never-list (except note bodies), the weekly scheduled task, and GitHub Actions scoring.

## Questions and choices

| Q | Question | Chosen | Why |
|---|---|---|---|
| Q1 | What may the loop change about itself? | Everything: its own `SKILL.md`, scorecard, thresholds and guardrails, each as a PR the user merges. The loop's direct changes (PRs) cover domain-repo files only; changes to the loop's own `SKILL.md`, scorer or anything else in `mnemo` go out as issues (Q3, Q7). (Clarified by architecture Q12: the Mnemo copy inside a domain repo, meaning `.claude/skills/mnemo-*`, `.claude/mnemo/` and the Mnemo hook entries in `.claude/settings.json`, is not a "domain-repo file" here. It is `mnemo`'s, changed only by `mnemo-setup`, so a change to it goes out as an issue.) | User's pick: full recursion |
| Q2 | Do the 2026-11-15 guardrails still bind it? | No; Q1 replaces them. Kept: no edits to note bodies (`sources/`, `attachments/` included), and counts-only across domains | User's pick. Counts-only stays because a PR or issue exposes its contents before review, and personal data is a protected rule |
| Q3 | Where do learned rules land? | Domain-specific → that domain's `_meta/conventions.md` via PR. Everything else → a GitHub issue on `mnemo`, which the user turns into an OpenSpec change | The loop never edits this repo; OpenSpec and version-bump rules hold; releases stay tag-based (architecture Q10) |
| Q4 | What starts a run? | On demand only: "run Mnemo maintenance" in a domain session. No scheduled task | No research-preview task, no silent 72-hour shutdown, plan usage only when the user chooses |
| Q5 | What does each loop PR show? | Diff, scorecard, and provenance per change (the query-log lines: date, result type, opened/cited paths). Changes to the loop, scorer or guardrails go in a separate `mnemo:meta` PR, marked by a `[meta]` title prefix, not a label (structure Q14). Scorecard shows run count and variation per figure | The user's merge is the only gate; provenance catches poisoned or drifting proposals |
| Q6 | How big is the scorecard? | Targeted by default: the triggering question + 2 paraphrases + every test question whose answering note the change edits, 3 answers per side (`main` vs branch). Every `mnemo:meta` PR runs the full set | Cost scales with the change; the riskiest changes get the full comparison |
| Q7 | How does an approved proposal reach `mnemo`? | The session opens the issue itself, as `/cla:report-upstream` does: target from `plugin.json` `repository`; search open issues first; comment on an open match, else create one; all through `gh api` (REST), because `gh issue` is blocked in cloud sessions; only after the user approves the issue text in the session. The target is the `repository` field in `plugin.json`, once added. (Target replaced by architecture Q12–Q14: a domain repo has no `plugin.json`. The target is the `repository` key of the domain's stamp file, `.claude/mnemo/stamp.json`, which `mnemo-setup` writes from its copy tool's `UPSTREAM_REPOSITORY` constant. When the key is missing or empty, improve stops and asks the owner.) | Proven pattern with dedupe built in |

## Added after the first pass (2026-11-16): query-log line format

| Q | Question | Chosen | Why |
|---|---|---|---|
| Q8 | What does each query-log line record? | One JSON object per line, in `_meta/query-log/YYYY-MM.jsonl`, with keys `date`, `q`, `opened` (list), `cited` (list), `result` (`answered` / `not-found` / `corrected`) and `user` (the user's words on a correction). Example: `{"date": "2026-11-16", "q": "...", "opened": ["<path>"], "cited": [], "result": "not-found", "user": ""}` | The log is the loop's only input and Q5's provenance; this format supports every signal in report section 3 (e.g. opened but never cited). Any character in a question is safe, and the Python stdlib `json` reads it. This replaces the report's pipe format |
| Q9 | Who commits the recall query-log line? | Recall only appends its log line. The end-of-turn (Stop) hook commits and pushes it right away, through `mnemo_check.py save` (structure Q12, Q13). Before appending a question, recall writes `<redacted>` over any secret-pattern match (structure Q15). This changes architecture Q7's "recall commits its query-log line" | One committer for the log; the hook already runs every check first |
| Q10 | How can a domain session file an issue on `mnemo`? | Each domain repo's `CLAUDE.md` rule becomes "never add another repository, except `mnemo`, and only to file an approved loop issue". `mnemo` holds no notes, so no domains mix. A device test confirms the exception lets nothing else through. (Unchanged by architecture Q13. `mnemo-setup` runs in a session on `mnemo`, not in a domain session, so setup needs no exception.) | Filing from a cloud session needs `mnemo` attached (report line 99) |

## Noted, not asked

- **Reversibility:** every change is a PR the user merges; git history is the undo.
- **Rate limits:** on-demand runs are far below 100 runs per hour per account.
- **Logging and personal data:** the loop reads the query log inside its own domain session; no new data flow.
- **Issue content:** counts, cause categories and proposed rule text only; never question text or note content.
- **Edge cases (spec defaults, revisable):** a run stops if a loop PR is already open in that domain; an empty query log ends the run with "no signals".
- **Test-set edits (default, revisable):** any change to the test set counts as `mnemo:meta`, so it gets its own PR and the full-set scorecard. Otherwise the loop could quietly make its own exam easier.
- **Accepted cost (Q4):** nothing improves unless the user starts a run.
- **Unverified, for the spec:** that `gh api` (REST) can list, comment on and create issues from a cloud session (report line 268 says `gh issue` fails there because GraphQL is blocked), and, in a device test, that the `mnemo` exception in the domain `CLAUDE.md` rule (Q10) lets nothing else through.

## Invariants

- Every loop change is a PR the user merges, or an issue on `mnemo` filed after the user approves in the session.
- The loop never edits note bodies, `sources/` or `attachments/`. The "note body" is everything below a note's frontmatter. Frontmatter fields the loop may change (`aliases`, `summary`, and, once added, the loop-owned `questions` and `links`; structure Q14) are not the body. `sources/` and `attachments/` are immutable.
- The two rules Q2 keeps (no note-body edits; counts-only across domains) are owner-only: no loop PR or issue may propose removing them.
- Scoring runs in the user's on-demand session (Q4), never on GitHub.
- Nothing leaving a domain carries question text or note content; counts, cause categories and rule text only.
- The loop never commits to `mnemo`; it only files or comments on issues.
- Added by architecture Q12: a loop PR never changes the Mnemo copy in a domain repo (`.claude/skills/mnemo-*`, `.claude/mnemo/`, the Mnemo hook entries in `.claude/settings.json`). A change there goes out as an issue on `mnemo`.
- A `mnemo:meta` PR (loop, scorer, guardrails, test set) is never batched with content changes, and always runs the full-set scorecard.
- Every proposed change cites the query-log lines behind it.
- No check or scoring runs on GitHub (architecture Q1).

## Final axes

All Clear: reversibility (Noted), invariants (Invariants section), downstream consumers (Q3, Q4), release (Q3), smaller option (Q4), edge cases (Noted), design elegance (Q4), recursion scope (Q1), rule location (Q3), scoring location (Q4), held-out set reach (Q2: user accepted the loop can see and edit test sets), cross-domain step (Q3), loop PRs vs repo rules (Q3), rule retirement (Q2), who files (Q7), issue content (Noted), review burden (Q5), rate limits (Noted), timeout and retry (Q4), cost (Q6), logging and personal data (Noted), abuse and injection (Q5), non-deterministic testing (Q6).

## Follow-ups

- Research design decision and report section 3: record that additive-only, the never-list, the weekly scheduled task and Actions scoring are replaced by this decision.
- Domain `CLAUDE.md` template (`mnemo-setup`): write the rule "never add another repository, except `mnemo`, and only to file an approved loop issue" (Q10).
- ~~`mnemo` `plugin.json`: add a `repository` field, so the issue target is read from the manifest (Q7).~~ Replaced by architecture Q12–Q14: `plugin.json` is removed. The `add-mnemo-setup` change writes the target into each domain's `.claude/mnemo/stamp.json` (`repository` key).

## Why it matters, and next step

It sets the rules for the one part of Mnemo that changes Mnemo itself, and makes the user's merge, backed by provenance and a full-set scorecard for meta changes, the only gate. Next: `/opsx:propose` the `mnemo-improve` change after the scaffold change from the structure decision lands, verifying the `gh` cloud check first.
