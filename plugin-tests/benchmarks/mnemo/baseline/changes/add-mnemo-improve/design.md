# Design

Trigger: security, a cross-cutting change, a new data model, and real ambiguity.
- Security: the skill writes the owner's files, scores its own changes, and sends text to another repository.
- Cross-cutting: it changes six capabilities owned by four earlier changes.
- Data model: the test-set file, the `questions` and `links` fields, and the `hubs/` and `archive/` rules.
- Ambiguity: the decisions leave the scorecard's pass rule, the log window, and the meta base side open.

See `proposal.md` for the why and the specs for the outcomes.

## Context

- `add-mnemo-recall` writes the input (`query-log`) and defines the answer rules the scorer reuses (`recall-answers`).
- `add-check-scripts` gives the check command (`check-interface`), the add-only base schema (`note-schema`), and the one-script rule (`plugin-release` "Shared files exist once").
- `add-guard-hooks` saves the session's working tree at each turn end (`end-of-turn-save`). That is why loop edits never sit in that tree (`improve-run` "Session working tree untouched").
- `add-mnemo-setup` owns the layout (`domain-layout`) and the domain wall with its `mnemo-plugin` exception (`domain-instructions` "Domain wall").
- `add-mnemo-review` forbids any skill starting review (`review-scan` "Started only by the owner").
- CLA `/cla:report-upstream` v2.3.0 (`skills/report-upstream/SKILL.md`) is the issue-filing pattern: §2 reads the target from the manifest's `repository` and stops if it is missing; §3 searches and comments on an open match; §4 creates from a body file. Two things differ here: REST calls only (§3–4 use `gh issue`), and the owner's approval of the exact text.

## Goals / Non-Goals

**Goals:** pin the log window, the signal thresholds, the scorecard numbers and pass rule, the branch and PR shapes, the issue shape, and the formats of the new metadata.

**Non-Goals:**
- moving notes into `archive/`; this change defines the folder only
- `mnemo_schema_version` (D11)
- a held-out test split (the decision's Final axes: the user accepted the loop can see and edit test sets)
- scheduled runs and GitHub Actions (Q4, architecture Q1)

## Decisions

**D1. Files.**
- `skills/mnemo-improve/SKILL.md`
- `references/signals.md` (D5)
- `references/scorecard.md` (D7)
- `references/pr-body.md`
- `references/issue-body.md` (D9)
- No new script, because `plugin-release` "Shared files exist once" allows only `mnemo_check.py`. Scorecard arithmetic is a few sums, done in the skill.

**D2. Guards, in order.** Each guard stops the run with nothing changed.
1. No git repo, or no `mnemo.schema.yml` at the top level.
2. Missing `hubs/`, `archive/` or `_meta/tests/questions.yml`. The skill names `/mnemo:mnemo-setup`, whose top-up adds them (structure Q5).
3. An open domain PR whose head branch starts with `mnemo-improve/`. It is found with `gh api repos/{owner}/{repo}/pulls?state=open` or the built-in GitHub tool. If the call fails, the run stops.

**D3. Log window.**
- The run covers lines dated on or after the date in the head branch name of the newest closed `mnemo-improve/` PR, merged or not.
- It reads that from `pulls?state=closed`, paginated. With no closed loop PR, it covers every line.
- A PR the owner closed unmerged consumes its signals, so a rejected proposal does not come back on every run.
- Rejected:
  - a cursor file, which is one more loop-owned file with its own `[meta]` PR
  - the whole log on every run, which re-proposes rejected changes
- Unreadable lines are recorded as `<month file>:<line>`. They never serve as provenance.

**D4. Branches and working copies.**
- Branches: `mnemo-improve/YYYY-MM-DD` (domain) and `mnemo-improve/YYYY-MM-DD-meta`. Both are cut from `origin/main`.
- Edits happen only in `git worktree add` copies under the system temp folder. Commits stage named paths there, so the commit guard's checks still run.
- Pushing uses `git push -u origin <branch>`, only after the owner's yes. The skill never calls `mnemo_check.py save`, because `save` pushes the current branch.
- PRs are opened with `gh api -X POST repos/{owner}/{repo}/pulls` or the built-in GitHub tool, never `gh pr` (report line 268).
- Titles:
  - `mnemo-improve: <n> changes, <first date> to <last date>`
  - `[meta] mnemo-improve: <n> changes, …` for the `[meta]` PR
- No labels (structure Q14).
- The worktrees are removed at the end, whatever the outcome.

**D5. Signals (`references/signals.md`).** A "miss" is a `not-found` or `corrected` line.

| Signal in covered lines | Proposal | Goes to |
|---|---|---|
| Miss, and a note answers it in other words | add the words to `aliases` (a name) or `questions` (a phrasing) | domain PR |
| `not-found`, and no note answers it | gap, listed | PR body or summary |
| Note in `opened` but not `cited`, in **2+** lines | new `summary` | domain PR |
| One topic in **3+** lines | new hub note, or new `links` entries on the existing hub | domain PR |
| Two notes both in `opened`, in **3+** lines | each added to the other's `links` | domain PR |
| `corrected` | listed with the owner's words; capture can apply it | owner |
| Two cited notes disagree | flagged | owner |
| One cause behind **3+** misses, specific to this domain | numbered rule `R<n>` in `_meta/conventions.md` | domain PR; `[meta]` if it steers the loop |
| A cause not specific to this domain | issue (D9) | `mnemo-plugin` |
| Each change in the domain PR | its triggering question added to the test set | `[meta]` PR |

- Q1 replaced additive-only, so a conventions rule may be reworded or removed. The two kept rules are the exception (`improve-guardrails`).
- A hub note gets a body only when it is created: its title and one line per linked note. After that only `links` and `summary` change, so "never edit a note body" holds for hubs too.
- Thresholds: 3 comes from the report's "3+". 2 for opened-not-cited is new, set to cut one-off noise.
- Rejected: 1 line per signal, which turns every stray open into a PR.

**D6. Provenance line.** Each change lists its lines, one per row:

`_meta/query-log/2026-11.jsonl:14 · 2026-11-16 · not-found · opened: <paths> · cited: <paths>`

The domain PR lives in the domain repo, so naming paths there leaves nothing outside the domain.

**D7. Scorecard (`references/scorecard.md`).** These numbers are pinned:

| Item | Value |
|---|---|
| Triggering questions per change | the `q` of each cited line, deduplicated, at most **3** (the newest) |
| Paraphrases per triggering question | **2**, written before any answer |
| Answers per question per side | **3** |
| Correct answer | cites at least one expected note |
| Change passes | each triggering question and paraphrase is correct at least **2 of 3** on the PR side |
| PR passes | every change passes, and the test-set total on the PR side is at least the base side's |

- Sides:
  - The domain PR compares `main` with its branch.
  - The `[meta]` PR compares `main` plus the domain branch with that plus the meta commits. That merge lives in a scoring-only worktree and is never pushed. With no domain PR, the base is `main`.
  - Why: a test question added for a fix fails on a meta branch cut from `main`, where the fix does not exist yet.
- Answerers:
  - Each answer comes from a fresh subagent. It gets only the question and a worktree path, and is told to follow `${CLAUDE_PLUGIN_ROOT}/skills/mnemo-recall/SKILL.md` without the log step. It returns the paths it cited.
  - The answer worktrees are thrown away, so nothing reaches the session's log (`improve-scorecard` "Scoring leaves the query log alone").
- Figures:
  - Each figure reads `k/3`.
  - Totals read `sum (min–max per run)`.
- Cost:
  - A targeted set of 4 questions costs 24 answers.
  - Before a full set, the skill states questions × 6 and asks.
- The verdict informs the owner and does not block: the owner's merge is the only gate (Q5). PRs open only after the owner's yes, so a fail never triggers an external write on its own.
- Rejected:
  - 1 answer per side, which cannot show variation (Q5)
  - a strict 3/3 pass, which fails on noise alone

**D8. Before any push.**
- On each branch, run `links`, `schema`, `deletions` and `secrets` with `--range origin/main..HEAD`, through `hooks/probe-python.sh` as capture's D2 does.
- A result other than 0 means report and stop for that branch (global rule: failures report, the owner decides).
- Then show one summary: the changes, the verdicts, the gaps, the owner's items and the unreadable count. Then ask once to push and open each PR.

**D9. Issues (`references/issue-body.md`).**
- Target: `repository` in `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`. This change adds `"repository": "https://github.com/crisradu75/mnemo-plugin"`. No earlier change in the batch adds it.
- Title: `mnemo-improve: <cause category>`. The category comes from a fixed list in `issue-body.md`, such as `date-range questions`, `name variants` or `summary drift`, plus `other: <3–6 words>`.
- The body has these fields only: plugin version; cause category; counts as `<result>: <n>` per month; proposed rule text; the skill it targets.
- Before showing the text, the skill checks that no `q` or `user` value of a covered line, and no note path or title, appears in it. A hit is removed, and the skill says so.
- Search: `gh api -X GET search/issues -f q='repo:<o>/<r> is:issue is:open in:title "<title>"'`. An exact-title match gets a comment through `POST repos/<o>/<r>/issues/<n>/comments`. With no match, the skill uses `POST repos/<o>/<r>/issues`.
- Bodies are sent with `--input <json file>` from the system temp folder (the owner's rule 9: body files, never inline).
- A closed match does not count. Q7 says "comment on an open match, else create one".
- Cloud sessions need `mnemo-plugin` attached (Q10). Device test 1.3 confirms it.

**D10. Formats.**
- Hub notes:
  - live at `hubs/<slug>.md`, with `type: hub`
  - carry the base fields and `links`
  - have no domain declaration
- Archived notes:
  - live at `archive/<type folder>/<name>.md`
  - carry `status: archived`
  - meet their type's fields and name pattern, but not its folder rule
  - A move there is a git rename, which the `deletions` check accepts.
- `questions` holds a list of phrasings. `links` holds a list of paths from the repo root. Both are inline lists, within the YAML subset of `note-schema`.
- The test set:
  ```yaml
  # Mnemo test questions. Changed only through a [meta] pull request.
  - q: "<question>"
    notes: [<path>, <path>]
    added: YYYY-MM-DD
    from: _meta/query-log/YYYY-MM.jsonl:<line>
  ```
  The file sits under `_meta/`, so the checks never read it. The skill reads it, and so does a test-only validator in `tests/`.

**D11. Deferred metadata, interpreted.**
- The brief scopes Q14's list to `questions`, `links`, `hubs/`, `archive/` and the test set.
- `mnemo_schema_version` stays out: nothing reads it, which is Q14's own reason to defer. Review and setup keep their rules about it.
- PR labels are replaced by the `[meta]` prefix.

**D12. Description and evals.**
- The description (176 characters): "Run Mnemo maintenance: read this domain's query log, propose metadata and conventions fixes as scored PRs, and file approved shared rules as plugin issues. Not for link checks."
- The 10 prompts that should trigger:
  - run Mnemo maintenance
  - improve recall from my query log
  - turn this month's misses into fixes
  - tune this domain's conventions from the misses
  - run the improvement loop
  - add aliases for questions recall missed
  - open the maintenance PR
  - update the test questions from recent misses
  - propose a shared rule for the plugin from my misses
  - why does recall keep missing things? fix it
- The 10 near-misses:
  - check my notes for broken links (review)
  - what did I note about <topic> (recall)
  - note that <fact> (capture)
  - set up a Mnemo domain (setup)
  - that answer was wrong, it is <fact> (recall)
  - open a PR for my code changes
  - file an issue about <bug> in <other repo>
  - run maintenance on the build server
  - summarise yesterday's git log
  - show me the query log file
- Pass mark: 18 of 20, on improve's set alone.

## Owner rules as invariants

| Rule | Checked by |
|---|---|
| Every proposed change cites query-log lines | static test on `pr-body.md`; scratch-run PR bodies list `file:line` for each change |
| Note bodies, `sources/` and `attachments/` are never edited | test: the diff of a scratch-run branch against `main` touches only `aliases`, `summary`, `questions` and `links` in existing notes |
| Nothing leaving a domain carries question text or note content | test: the filed scratch issue body holds no `q`, `user`, note path or title from the scratch domain |
| Never commits to `mnemo-plugin`; only files or comments on issues | static test: `SKILL.md` holds no `git clone`/`push` of the plugin repo and no `gh issue` or `gh pr`; the scratch target gains issues and comments only |
| The kept rules are owner-only | `improve-guardrails` "Log suggests lifting the body rule" |
| `[meta]` is never batched with content changes, and always gets the full set | scratch run: the meta PR diff touches only `_meta/tests/` and loop rules; its scorecard lists every test question |
| Scoring runs in the session, never on GitHub | `plugin-release` "Nothing runs on GitHub"; the log stays byte-identical after a scorecard |
| Every loop change is a PR the owner merges, or an approved issue | `main` on the scratch remote gains no loop commit; no push or API write before the yes |
| Issue filing only after the owner approves the text | transcript: the approval turn comes before every POST |
| A failure reports and stops | scratch runs with a refusing remote and a refusing target: no retry, no further write |

## Decision rows (verbatim)

| Source | Q | Chosen |
|---|---|---|
| self-improvement | Q1 | Everything: its own `SKILL.md`, scorecard, thresholds and guardrails, each as a PR the user merges. The loop's direct changes (PRs) cover domain-repo files only; changes to the loop's own `SKILL.md`, scorer or anything else in `mnemo-plugin` go out as issues (Q3, Q7) |
| self-improvement | Q2 | No; Q1 replaces them. Kept: no edits to note bodies (`sources/`, `attachments/` included), and counts-only across domains |
| self-improvement | Q3 | Domain-specific → that domain's `_meta/conventions.md` via PR. Everything else → a GitHub issue on `mnemo-plugin`, which the user turns into an OpenSpec change |
| self-improvement | Q4 | On demand only: "run Mnemo maintenance" in a domain session. No scheduled task |
| self-improvement | Q5 | Diff, scorecard, and provenance per change (the query-log lines: date, result type, opened/cited paths). Changes to the loop, scorer or guardrails go in a separate `mnemo:meta` PR, marked by a `[meta]` title prefix, not a label (structure Q14). Scorecard shows run count and variation per figure |
| self-improvement | Q6 | Targeted by default: the triggering question + 2 paraphrases + every test question whose answering note the change edits, 3 answers per side (`main` vs branch). Every `mnemo:meta` PR runs the full set |
| self-improvement | Q7 | The session opens the issue itself, as `/cla:report-upstream` does: target from `plugin.json` `repository`; search open issues first; comment on an open match, else create one; all through `gh api` (REST), because `gh issue` is blocked in cloud sessions; only after the user approves the issue text in the session. The target is the `repository` field in `plugin.json`, once added |
| self-improvement | Q8 | One JSON object per line, in `_meta/query-log/YYYY-MM.jsonl`, with keys `date`, `q`, `opened` (list), `cited` (list), `result` (`answered` / `not-found` / `corrected`) and `user` (the user's words on a correction). […] |
| self-improvement | Q9 | Recall only appends its log line. The end-of-turn (Stop) hook commits and pushes it right away, through `mnemo_check.py save` (structure Q12, Q13). […] |
| self-improvement | Q10 | Each domain repo's `CLAUDE.md` rule becomes "never add another repository, except `mnemo-plugin`, and only to file an approved loop issue". `mnemo-plugin` holds no notes, so no domains mix. A device test confirms the exception lets nothing else through |
| structure | Q14 | Deferred until `mnemo-improve` is built, then added under the add-only rule (Q7): the loop-owned `questions` and `links` fields, `hubs/`, `archive/`, `_meta/tests/questions.yml`, `mnemo_schema_version`, and PR labels. A `mnemo:meta` PR is marked by a `[meta]` title prefix, not a label. Per-type fields in a domain schema default to optional |

Self-improvement "Noted, not asked" (verbatim):
- **Issue content:** counts, cause categories and proposed rule text only; never question text or note content.
- **Edge cases (spec defaults, revisable):** a run stops if a loop PR is already open in that domain; an empty query log ends the run with "no signals".
- **Test-set edits (default, revisable):** any change to the test set counts as `mnemo:meta`, so it gets its own PR and the full-set scorecard. Otherwise the loop could quietly make its own exam easier.
- **Unverified, for the spec:** that `gh api` (REST) can list, comment on and create issues from a cloud session (report line 268 says `gh issue` fails there because GraphQL is blocked), and, in a device test, that the `mnemo-plugin` exception in the domain `CLAUDE.md` rule (Q10) lets nothing else through.

Self-improvement Invariants (verbatim):
- Every loop change is a PR the user merges, or an issue on `mnemo-plugin` filed after the user approves in the session.
- The loop never edits note bodies, `sources/` or `attachments/`. The "note body" is everything below a note's frontmatter. Frontmatter fields the loop may change (`aliases`, `summary`, and, once added, the loop-owned `questions` and `links`; structure Q14) are not the body. `sources/` and `attachments/` are immutable.
- The two rules Q2 keeps (no note-body edits; counts-only across domains) are owner-only: no loop PR or issue may propose removing them.
- Scoring runs in the user's on-demand session (Q4), never on GitHub.
- Nothing leaving a domain carries question text or note content; counts, cause categories and rule text only.
- The loop never commits to `mnemo-plugin`; it only files or comments on issues.
- A `mnemo:meta` PR (loop, scorer, guardrails, test set) is never batched with content changes, and always runs the full-set scorecard.
- Every proposed change cites the query-log lines behind it.
- No check or scoring runs on GitHub (architecture Q1).

Self-improvement Follow-ups (verbatim), and where each lands:
- "Research design decision and report section 3: record that additive-only, the never-list, the weekly scheduled task and Actions scoring are replaced by this decision." This is outside this repo, so it is listed in `tasks.md` Workflow follow-up.
- "Domain `CLAUDE.md` template (`mnemo-setup`): write the rule …" This is done by `add-mnemo-setup` (`domain-instructions` "Domain wall").
- "`mnemo-plugin` `plugin.json`: add a `repository` field, so the issue target is read from the manifest (Q7)." This change does it (task 1.5).

`[…]` marks text cut because it does not bear on this skill.

## Risks / Trade-offs

- [A model-written paraphrase can be too close to the original, so the question passes too easily] → `scorecard.md` requires each paraphrase to share no content word with the triggering question beyond names. Paraphrases are listed in the PR, so the owner sees them.
- [Scorecard cost grows with the test set] → the skill states the full-set count and asks first. Task 1.6 measures one answer's cost.
- [Fresh subagents may be unavailable in a cloud session] → task 1.4 checks this first. Without them, the run stops before scoring, never scoring in its own context.
- [A loop PR merged with conflicts against later captures] → the PR only touches frontmatter and new files. GitHub shows any conflict before the merge.
- [The window keys on branch-name dates, and two runs on one day share a date] → only one run can be open at a time (D2), and a same-day re-run covers the same lines again. Changes already merged produce empty diffs.
- [Issue text could still carry a question through the rule text] → the D9 substring check, plus the owner's approval of the exact text.

## Migration Plan

- Merge last in the batch, after `add-mnemo-recall` and `add-mnemo-review`. The six MODIFIED or ADDED deltas need those changes archived first: `openspec validate` reports that archive refuses a delta whose target spec does not exist yet.
- Existing domains gain `hubs/`, `archive/`, `_meta/tests/` and the test set through a setup top-up.
- The base schema only grows optional fields, so no note is rewritten.
- Rollback: revert the PR. The added fields stay valid extra fields under `note-schema` "Optional and extra fields".
