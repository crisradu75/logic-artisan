# Prompt audit, part A: report

Read-only. The only files written are this report and `A-diff.md` (same folder). Paths below are
relative to `C:\Code\logic-artisan\.claude\plugins\cla\` unless absolute.

## Step 0: scope and target assumptions

- **Scope.** `skills/_shared/` (README plus 21 reference files; `required-permissions.json` and
  the three scripts exist and were checked for existence only), `agents/*.md`, `output-styles/*.md`,
  and SKILL.md plus references for annotate, checkpoint, codify-learnings, diagnose, feedback,
  new-worktree, report-upstream, right-model, save-permissions, shape-decision, spec-to-pr-retro.
  Settings files and `.mcp.json` were not read. Not audited: lite-pr, multi-*, spec-to-pr,
  review-change, project-review, cla-setup, codify-retro, sync-context, hooks, scripts, `lib/`
  (they were grepped only to confirm that cited paths, flags and headings exist).
- **Target model.** Claude Opus 5.5 for every file with no pin (read against "Migrating to Claude
  Opus 5.5", behavioral shifts). Sessions launch on Sonnet, so Claude Sonnet 5.5 behavioural shifts
  were applied to skill bodies a Sonnet session executes. `agents/doc-sweeper.md` and
  `agents/fact-gatherer.md` pin `model: haiku`, so they were read against Claude Haiku 5.5.
- **Not audited as code.** No request-building code or tool definitions are in scope. Group 3 is
  not applicable. Group 4: not applicable, except the sub-agent roster check (see Group 4 below).
- **Never invoked, per the owner.** annotate, diagnose, save-permissions and spec-to-pr-retro are
  in scope and have never been invoked; codify-retro and sync-context are out of scope. Absence of
  a failure is not evidence a rule works for those four, so findings against them rest on the
  repository, not on use. No retirement is recommended.

## Summary

Highest-impact findings:

1. **A1.** The `new-worktree` env-file snippet opens with `cd <app-dir>`. The plugin's own guard
   (`hooks/block-cd-in-bash.py`) blocks a leading `cd`, and `bash-discipline.md:7` forbids it. A
   Sonnet session following the skill literally trips its own guard.
2. **A3, A4, A5, A2.** Four stale references: `skill-authoring.md:3` names `spec-to-pr/references/ship.md`
   (moved to `_shared/references/` on 2026-11-11); `model-routing.md:49-50` says the two haiku
   agents are "low (body-instructed)" and neither body says that; `annotate/SKILL.md:106-111` uses a
   bare `$CLAUDE_PLUGIN_ROOT` that `plugin-root.md` says is not a Bash variable; `new-worktree/SKILL.md:34-35`
   points to a memory entry no repo has.
3. **A21, A22, A20.** Style and skill text that Opus 5.5 and Sonnet 5.5 read literally: a ban on
   "play-by-play narration" (both models under-narrate), numeric sentence ceilings in the output
   style, and "keep this to the fewest possible tool calls" in `new-worktree`.

Counts (findings with a proposed hunk, plus low-confidence flags):

| Group | High | Medium | Low (flag only) | Total |
|---|---|---|---|---|
| 1 Dated prompt text | 0 | 9 | 2 | 11 |
| 2 Brittle skill and configuration files | 5 | 9 | 4 | 18 |
| 3 Tool descriptions | not applicable | | | 0 |
| 4 Request config and architecture | not applicable (no request code); roster check: zero | | | 0 |

Group 1 by row: 1a pressure language 0, 1b scaffolds 0, 1c over-specification 0 Medium and 1 Low
(L3), 1d fossils 7 Medium (A13-A17 migration-relative phrasing, A20 tool-use discouragement, A21
update suppressor), 1e prohibition clusters 0, 1f output-shaping 2 Medium (A22, A23) and 1 Low (L6).
Group 2: contradictions or stale facts A1-A10 (5 High, 5 Medium), history narratives A11, A12, A18,
A19 (4 Medium), low flags L1, L2, L4, L5.

**Surface otherwise clean.** Emphasis density is low everywhere (the highest is 9 caps words in
the 4,100-word `subagent-brief.md`, all on reasoned prohibitions). No `think step by step`, no
scratchpad or thinking tags, no prefill, no thinking-depth prose, no visual-input scaffolding, no
grader vocabulary. The model-routing and orchestration-economy copies of the review-sizing and
cost rules agree with each other (see "Cross-file duplicates").

## Inventory (word counts from `wc -w`)

41 files, 41,772 words.

| File | Words |
|---|---|
| skills/_shared/README.md | 925 |
| skills/_shared/references/base-branch-resolution.md | 156 |
| skills/_shared/references/bash-discipline.md | 1,095 |
| skills/_shared/references/chain-merge.md | 2,498 |
| skills/_shared/references/conflict-resolution.md | 808 |
| skills/_shared/references/economy-rules-file.md | 499 |
| skills/_shared/references/instruction-files.md | 207 |
| skills/_shared/references/model-routing.md | 2,288 |
| skills/_shared/references/orchestration-economy.md | 858 |
| skills/_shared/references/past-offenses.md | 188 |
| skills/_shared/references/plugin-root.md | 239 |
| skills/_shared/references/precheck.md | 367 |
| skills/_shared/references/retiring-specs.md | 587 |
| skills/_shared/references/review-sweeps.md | 629 |
| skills/_shared/references/run-log-schema.md | 612 |
| skills/_shared/references/runtime-rules.md | 469 |
| skills/_shared/references/ship.md | 1,554 |
| skills/_shared/references/skill-authoring.md | 1,115 |
| skills/_shared/references/subagent-brief.md | 4,137 |
| skills/_shared/references/terminology-format.md | 139 |
| skills/_shared/references/test-quality-gates.md | 3,493 |
| skills/_shared/references/test-quality.md | 346 |
| agents/doc-sweeper.md (haiku) | 704 |
| agents/fact-gatherer.md (haiku) | 667 |
| output-styles/CLA.md | 836 |
| output-styles/COPILOT.md | 239 |
| skills/annotate/SKILL.md | 2,443 |
| skills/checkpoint/SKILL.md | 647 |
| skills/codify-learnings/SKILL.md | 1,048 |
| skills/codify-learnings/references/routing.md | 1,111 |
| skills/diagnose/SKILL.md | 1,441 |
| skills/diagnose/references/strategies.md | 814 |
| skills/feedback/SKILL.md | 1,418 |
| skills/new-worktree/SKILL.md | 1,745 |
| skills/new-worktree/references/path-casing.md | 697 |
| skills/report-upstream/SKILL.md | 874 |
| skills/right-model/SKILL.md | 802 |
| skills/save-permissions/SKILL.md | 814 |
| skills/shape-decision/SKILL.md | 1,235 |
| skills/shape-decision/references/question-form.md | 342 |
| skills/spec-to-pr-retro/SKILL.md | 686 |

Always-loaded versus on-demand: only `output-styles/CLA.md` (forced for the plugin) and each skill
description ride on every session; everything else loads on invocation or dispatch.

## Facts checked (each by reading, glob or grep, never by running a command)

Exist: `_shared/scripts/{git_state,check_spec_proof,check_no_project_tokens}.py`,
`_shared/references/required-permissions.json` (holds `Bash(gh *)` and `Bash(python3 *)`, as
`chain-merge.md` says), `annotate/scripts/*` (render_doc, render_html, render_change, annotate_server,
annotations_store, sweep_changes; default port 8741 and `--no-open` present),
`new-worktree/scripts/manual_worktree.py` (`--name`, `--diagnose`), `spec-to-pr-retro/scripts/spec_to_pr_aggregate.py` (`--limit`, `--log`
present; reads `fleet.local.md`), `lib/log_run.py` (`SHAPES` at line 199), the `plugin.json`
`repository` field, `block-worktree-path-escape.py`, `ask-destructive-git.py` (`ALLOW_PR_MERGE`),
`spec-to-pr/references/{design-tradeoffs (## Ship), concurrent-runs, archive, handoff}.md`,
`multi-pr/references/cleanup.md` (step 2), `multi-lite/SKILL.md` ("Never end a turn with nothing
in flight"), `review-change/references/{checklist,dispatch}.md` (0a-0h range matches), the
`--pr-base` and `--no-tree-check` flags in `spec-to-pr/SKILL.md`, `openspec/config.yaml`
(`requirement:` / `manual:` task rule), `plugin-tests/tests/conformance/test_skill_lint.py`,
`plugin-tests/tests/skills/_shared/test_git_state.py`.

Not found or contradicted: see A1-A6 and A10 below.

## Findings (ordered by confidence, then by id)

Fields: Location / Evidence / Pattern / Why obsolete / Confidence / Action. `Dxx` points at the
hunk in `A-diff.md`.

### High

**A1. Location:** `skills/new-worktree/SKILL.md:91-99`.
**Evidence:** snippet begins `cd <app-dir>` then `MAIN="$(dirname "$(git rev-parse --git-common-dir)")"`.
Blame: line 92 from the 2026-07-23 extraction commit `ee4034ad`. Contradicted by
`hooks/block-cd-in-bash.py` (docstring: blocks "leading `cd `" and ` && cd `; allows only quoted text,
subshells, `pushd`/`popd`) and `skills/_shared/references/bash-discipline.md:7` ("Compound bash: `cd <path> && <cmd>`... Use absolute paths ... `git -C <abs-path>`").
**Pattern:** Group 2, instruction files that contradict each other (skill against a shared reference and a guard).
**Why obsolete:** the guard is newer than the skill text and the repository states the rule in two places; a literal-reading Sonnet session runs the snippet and is blocked, or routes around the guard (the hook's own docstring records that happened once).
**Confidence:** High (repository contradiction). **Action:** rewrite (D: A1): use `git -C <app-dir>` and an absolute destination, no `cd`.

**A2. Location:** `skills/new-worktree/SKILL.md:34-35`.
**Evidence:** "(Full incident writeup: see a per-user note.)"
**Pattern:** Group 2, volatile specifics / history narratives (a path that resolves nowhere).
**Why obsolete:** it names a per-user note that no repo holds, and a consuming repo has no such note. The rule above it already carries its reason.
**Confidence:** High (named path does not exist). **Action:** remove the sentence (A2).

**A3. Location:** `skills/_shared/references/skill-authoring.md:3`.
**Evidence:** "its `references/{ship,revise,archive,handoff}.md` show the split in practice." Blame 2026-08-14.
**Pattern:** Group 2, volatile specifics.
**Why obsolete:** `skills/spec-to-pr/references/` holds archive, branch-and-pr-base, concurrent-runs, design-tradeoffs, handoff, implement-delegate, revise, scope-asks, test-notes, workflow-diagram. `ship.md` moved to `_shared/references/` on 2026-11-11 (`91ce44f7`, #491).
**Confidence:** High. **Action:** rewrite (A3).

**A4. Location:** `skills/_shared/references/model-routing.md:49-50`.
**Evidence:** `| ... | haiku | low (body-instructed) | agents/fact-gatherer.md |` and the same for `doc-sweeper.md`. Blame 2026-08-10.
**Pattern:** Group 2, volatile specifics (claim about two files in the same tree).
**Why obsolete:** neither agent body mentions effort; grep for `effort` over `agents/*.md` returns nothing. Line 30-31 says the agents get "an output instruction in their body", which is true; the effort claim is not.
**Confidence:** High. **Action:** rewrite to "inherited" (A4).

**A5. Location:** `skills/annotate/SKILL.md:106-111`.
**Evidence:** `python3 "$CLAUDE_PLUGIN_ROOT/skills/annotate/scripts/render_doc.py" <path>` (four lines). Blame 2026-08-22; the repo's rule in `_shared/references/plugin-root.md` was written 2026-10 (`4c88d123`, `fc5b2895`).
**Pattern:** Group 2, instruction files that contradict each other.
**Why obsolete:** `plugin-root.md:12` says the placeholder "is **not** an environment variable in the Bash tool", and that a `SKILL.md` body arrives with `${CLAUDE_PLUGIN_ROOT}` already substituted. The bare, unbraced `$CLAUDE_PLUGIN_ROOT` is not that placeholder; an unset variable expands to nothing and runs `/skills/annotate/...`. `plugin-root.md` is the newer file. Every other skill in the tree uses the braced form (grep: no other bare use).
**Confidence:** High (repository contradiction). **Action:** rewrite (A5).

### Medium

**A6. Location:** `skills/_shared/references/bash-discipline.md:3`.
**Evidence:** "The same rules also live in the project's root `CLAUDE.md`; this file is the orchestrator's local enforcement reference." Blame 2026-09-23.
**Pattern:** Group 2, volatile specifics.
**Why obsolete:** this repo's root `CLAUDE.md` holds none of these rules (grep for `heredoc`, `git add -A`, `--body-file` returns nothing; it names only `block-cd-in-bash`). A consuming repo's `CLAUDE.md` is not written by the plugin (`cla-setup` has no such text). A claim a reader will try to verify and cannot.
**Confidence:** Medium. **Action:** remove the sentence (A6).

**A7. Location:** `skills/_shared/references/model-routing.md:26,28` (also `:146-147`, `right-model/SKILL.md:78-80`, `project-review/SKILL.md:42`).
**Evidence:** "**no** (inherits session)" for `Agent(...)`; "**no** (no effort key exists)" for agent frontmatter. Blame 2026-10-12 and 2026-10-26.
**Pattern:** Group 2, volatile specifics about a tool the harness owns.
**Why obsolete:** the `Agent` tool schema in this session has an `effort` parameter (restricted: set only when the user or a skill explicitly asks). The audit reference says some agents accept `effort` in a subagent definition. I did not read Claude Code's subagent docs, so this is not High.
**Confidence:** Medium. **Action:** rewrite (A7); the owner should confirm on the current docs first. The three other lines repeat the claim and need the same edit.

**A8. Location:** `skills/_shared/references/runtime-rules.md:19`.
**Evidence:** "write it to `temp/` and hand the path to a delegate".
**Pattern:** Group 2, two files ruling on the same point differently.
**Why obsolete:** `bash-discipline.md:11` (blame 2026-09-23 era, listed as hard rules) says scratch goes to the session scratchpad, and `temp/` only after `git check-ignore -q temp/` passes; "Nothing here makes `temp/` ignored". `runtime-rules.md` states `temp/` unconditionally. `orchestration-economy.md:35` adds a third spot (`scratchpad/<change-name>/` in the repo). The first two disagree; the third is a deliberate per-agent folder.
**Confidence:** Medium (older/newer order not established by blame; the stricter file is the one marked hard rule). **Action:** rewrite to point at bash-discipline (A8).

**A9. Location:** `skills/_shared/references/retiring-specs.md:26`.
**Evidence:** "These were reproduced on OpenSpec 1.14.1." Blame 2026-10-15 (`a0388428`).
**Pattern:** Group 2, volatile specifics.
**Why obsolete:** the repo upgraded to OpenSpec 2.0 on 2026-11-15 (`cbcdc05f`, #506). Nothing in the tree says the five traps still reproduce.
**Confidence:** Medium (not contradicted, only unverified since the upgrade). **Action:** rewrite to add a re-check (A9).

**A10. Location:** `skills/new-worktree/references/path-casing.md:41-43`.
**Evidence:** "(`hooks.json` carries the same `python3 || py || python` probe chain for exactly this reason.)"
**Pattern:** Group 2, volatile specifics.
**Why obsolete:** `hooks/hooks.json` now runs `hooks/probe-python.sh`; the chain (`for _c in python3 py python`, line 214) lives there, and the `hooks.json` description says so.
**Confidence:** Medium (the claim is half true: the chain exists, in another file). **Action:** rewrite (A10).

**A11. Location:** `skills/_shared/references/test-quality-gates.md:22-28`.
**Evidence:** "Measured in one session (2026-08-23)... one sat at `>= 55` against a real 83 ... and is now `>= 80` ... Quote the *current* value when citing one".
**Pattern:** Group 2, history narratives with a number that rots (CLAUDE.md check 3: a measurement holds only for the code it ran on).
**Why obsolete:** the passage tells the reader not to repeat the numbers it then prints; "is now `>= 80`" is a source-repo fact a consuming repo cannot check. The lesson (derive the floor from the real count) is already stated in the paragraph above it.
**Confidence:** Medium. **Action:** rewrite as an illustration (A11). The rule of keeping an incident's reason supports keeping the "why"; the dates and "is now" values are what goes.

**A12. Location:** `skills/_shared/references/test-quality-gates.md:274-287`.
**Evidence:** "Measured, in the source repo (`f0e8dd7`) ..." and "its message claimed ... covered that exact spelling since `865d366`".
**Pattern:** Group 2, history narratives (commit SHAs, a commit-message anecdote).
**Why obsolete:** SHAs from the source repo do not resolve in a consuming repo; the closing lesson ("a green targeted run is evidence about the target and nothing else") is repeated at lines 309-313.
**Confidence:** Medium. **Action:** rewrite (A12).

**A13. Location:** `skills/_shared/references/base-branch-resolution.md:7-9,11-14`.
**Evidence:** "The harness used to hardcode `master`..." and "previously copy-pasted identically into each SKILL.md".
**Pattern:** Group 1d, migration-relative phrasing.
**Why obsolete:** the text is a diff against an earlier version the model never saw; the current rule is "resolve, never assume".
**Confidence:** Medium. **Action:** rewrite (A13).

**A14. Location:** `skills/_shared/references/conflict-resolution.md:3-7`.
**Evidence:** "and, until this file existed, all four stopped at 'halt and surface'". Blame 2026-08-14.
**Pattern:** Group 1d, migration-relative phrasing.
**Confidence:** Medium. **Action:** rewrite (A14).

**A15. Location:** `skills/_shared/references/model-routing.md:8-15`.
**Evidence:** "**Shared, and now filed as such.** ... It lived under `spec-to-pr/references/` until the skills that depend on it outnumbered its nominal owner".
**Pattern:** Group 1d, migration-relative phrasing.
**Confidence:** Medium. **Action:** rewrite (A15).

**A16. Location:** `skills/_shared/README.md:10-14`.
**Evidence:** "These files were previously under `skills/spec-to-pr/references/`...".
**Pattern:** Group 1d, migration-relative phrasing. (The README is not scanned by the token guard and is read by humans and maintainers; still, it loads when a skill follows a pointer here.)
**Confidence:** Medium. **Action:** rewrite (A16).

**A17. Location:** `skills/report-upstream/SKILL.md:10-14` and `:38-40`.
**Evidence:** "which is exactly what happened before this existed: one launcher bug was diagnosed and fixed separately in three repos" and "the file-based predecessor of this channel".
**Pattern:** Group 1d migration-relative phrasing; Group 2 history narrative.
**Confidence:** Medium. **Action:** rewrite (A17). The rule keeps its reason (a stale "unfixed upstream" claim wastes triage).

**A18. Location:** `skills/save-permissions/SKILL.md:70`.
**Evidence:** "(Recurred once already on 2026-07-11 ... recurred again on 2026-07-16 when several non-destructive-looking wildcards ... were judged 'narrow'...)" plus "Do NOT" and "there is no such exemption". Blame 2026-07-23 (`ee4034ad`). Never invoked per the owner.
**Pattern:** Group 2, recency trap and history narrative; Group 1a emphasis; the owner's 2026-11-17 decision (absolute rules rewritten with scope and reason).
**Why obsolete:** the rule itself is a safety gate (a wildcard grant) and stays (keep-list items 3 and 5). The dates and the list of commands add nothing the rule needs; the reason (a wildcard grants every future command of that shape) is missing and is what the rewrite adds.
**Confidence:** Medium. **Action:** rewrite (A18).

**A19. Location:** `skills/feedback/SKILL.md:56` and `:61`.
**Evidence:** "(an incident id)" and "a copy of it in this sentence once went stale in the commit that changed the list".
**Pattern:** Group 2, history narratives (incident id; a note about the file's own edit history).
**Why obsolete:** the named incident file is not in `cla.io/feedback/` (only `field-guide-audit-2026-08-05.md`, `harness-observations-2026-08-14.md`, `notes.md`); grep finds it cited only in this skill and in `multi-spec/references/plan-schema.md`. The reason ("uncommitted files are what get lost") survives without the id.
**Confidence:** Medium. **Action:** rewrite (A19).

**A20. Location:** `skills/new-worktree/SKILL.md:18-20` (and `:49-54`, `:127-131`).
**Evidence:** "keep this to the fewest possible tool calls, and don't add 'just to be sure' verification steps"; "Don't spend a tool call checking whether you are in a worktree first".
**Pattern:** Group 1d, tool-use discouragement.
**Why obsolete:** the Sonnet 5.5 migration notes say it "follows these literally" ("minimize tool calls"), and CLA sessions launch on Sonnet. Blame 2026-08-07 (`eac349603`), tuned against an older model. The cost reason (each round-trip is a model call) is real and stays; the absolute form should become a rule scoped to commands whose output already confirms success.
**Confidence:** Medium. **Action:** rewrite lines 18-20 (A20). Lines 49-54 and 127-131 restate the same idea with their own reasons and were left alone.

**A21. Location:** `output-styles/CLA.md:33`.
**Evidence:** "- **Play-by-play narration.** A plan posted once before a long task is not narration." Blame 2026-10-07 (`07abaef0`, a context-shrinking commit).
**Pattern:** Group 1d, update suppressors written for chatty models.
**Why obsolete:** Opus 5.5 and Sonnet 5.5 are named in the audit reference as models that under-narrate when such a line is present, and the style is `force-for-plugin`. The style already protects a plan before a long task; it has no line saying when a finding is worth a sentence mid-run. The Opus 5.5 section recommends exactly such a line.
**Confidence:** Medium. **Action:** rewrite (A21).

**A22. Location:** `output-styles/CLA.md:85,87,88`.
**Evidence:** "Instructions: 20 words or fewer per sentence ... Explanations: 25 or fewer"; "over the ceiling → split it"; "six sentences or fewer".
**Pattern:** Group 1f, numeric output ceilings written against an older model's verbosity.
**Why obsolete:** the audit reference says a stated reason ("readable on first pass") does not turn a numeric clamp into a keeper; restate the goal. The first line of the style already states the goal ("The reader understands each sentence on the first pass"). The owner may reasonably decline: these numbers are a deliberate readability standard, set before Opus 5.5.
**Confidence:** Medium. **Action:** rewrite (A22).

**A23. Location:** `skills/annotate/SKILL.md:143-145`.
**Evidence:** "The whole report is four lines: what was built ..., the URL, where annotations land, and how to stop the server."
**Pattern:** Group 1f, numeric output ceiling.
**Why obsolete:** the four items are enumerated, so the count adds only a clamp. Never invoked.
**Confidence:** Medium. **Action:** rewrite (A23).

### Low (flag only, no hunk)

**L1. Location:** `output-styles/CLA.md:57-81` against an owner rule outside the repo.
**Evidence:** the style makes every finished interactive piece of work end with a "What's next ... offered as a `[y/n]`" line, which blame shows was tightened 2026-10-26 and 2026-11-02.
**Pattern:** Group 2, instruction files that contradict each other. The preference lives outside the project and carries no date, so the direction cannot be set from blame, and the fix would loosen a prompt rule.
**Confidence:** Low. **Action:** flag. The owner decides which governs interactive finishes.

**L2. Location:** `skills/_shared/references/runtime-rules.md:18`. "Pipe verbose command output through `head`/`tail`" against an owner rule outside the repo. Different cases; only a risk of misreading. Low. Flag.

**L3. Location:** `skills/shape-decision/SKILL.md:26-55`. Eight checklist axes plus six outside-service sub-axes, three levels with quoted evidence, Noted lines, a cold check. Pattern: Group 1c step-by-step choreography and patch accretion (blame shows additions across 2026-10 and 2026-11). It is an owner-tuned protocol that makes decisions auditable; no incident or measurement says it should shrink. Low. Flag.

**L4. Location:** `skills/_shared/references/subagent-brief.md:270-307` ("Measured in one chain: four delegates stalled this way, and only one of the four ever returned again"). The rule carries its reason; the counts are one chain's measurement with no command named (CLAUDE.md check 3). Low. Flag; keep the rule.

**L5. Location:** `skills/annotate/SKILL.md:188-190`. "Those percentages come from `scripts/sweep_changes.py` over 355 real changes" (51% not checkable, 22% covered). The command is named, which satisfies check 3, but `openspec/changes/archive` holds 60 directories today, so "355" cannot be re-run here. Low. Flag. Never invoked.

**L6. Location:** `skills/spec-to-pr-retro/SKILL.md:42` ("Under 40 lines"), `skills/codify-learnings/SKILL.md:101` ("at most 150 words"), `skills/_shared/references/orchestration-economy.md:8` ("about 300 words"). Numeric report caps (Group 1f). The 300-word figure is covered by an owner rule outside the repo, so it is protected policy; the other two are report shapes with listed contents. Low. Flag.

Total: 5 High, 18 Medium, 6 Low = 29 findings (L1-L6). Each finding is counted once, in the group of its main pattern.

## Cross-file duplicates and conflicts (Group 2)

Greps over the whole `.claude/plugins/cla/` tree:

- **Review-sizing / risk rule** (grep `Review sizing by risk|review-sizing|Low risk, docs`: 14 files, including `model-routing.md` as the canonical copy, `economy-rules-file.md`, `cla-setup/references/economy-rules-block.md`, `ship.md:115`, `spec-to-pr/references/revise.md`, `lite-pr/SKILL.md`, `README.md`). The copies I read (model-routing, economy-rules-file, ship, revise rows) agree on: low-risk docs gets `comment-analyzer` on Sonnet, low-risk code gets `code-reviewer` on Sonnet, high risk adds `silent-failure-hunter` on Opus, prose-dominant adds the skill reviewer, unsure means high. Agree; keep-list item 8 protects them. No disagreement found.
- **Never-end-a-turn rule** (grep: `multi-lite`, `multi-pr`, `multi-spec`, `spec-to-pr`, `chain-merge.md`). `chain-merge.md` (900 s watchdog, "a completion notification wakes the session") agrees with `multi-lite/SKILL.md:37` (the 1500 s watchdog serves a different case, a seam with nothing to dispatch). Agree.
- **`${CLAUDE_PLUGIN_ROOT}` resolution** (`plugin-root.md`, `new-worktree/SKILL.md:10-16`, six skills carry the short form). Agree. The one disagreeing copy is `annotate/SKILL.md` (A5).
- **Scratch location**: `bash-discipline.md:11` against `runtime-rules.md:19` (A8). Disagree.
- **Effort is not dialable on `Agent`**: `model-routing.md:26,146`, `right-model:79`, `project-review:42` agree with each other and disagree with the `Agent` tool schema (A7).
- **Diff-review rule / reviewers keep Bash and Edit**: `model-routing.md:39-42` and `subagent-brief.md:119-125` agree, and `docs/evidence.md` ("Guard decisions of 2026-11-04", lines 340-347) records the owner's decision to keep it. Not a finding.
- **`ALLOW_PR_MERGE=1`**: `chain-merge.md:161-170` agrees with the hook docstring and with `docs/evidence.md:349-356`. Not a finding.

## Group 4: sub-agent roster

`doc-sweeper` and `fact-gatherer` share a tool allowlist and a model, but their tasks and output
shapes differ (grep a symbol list and return a hit list with a scanned-files footer, against verify
claims and return a pass/fail table). Not redundant. Zero findings. Both are read-only through
`tools: ["Read","Grep","Glob"]`, which is the mechanical form `subagent-brief.md:363-376` asks for.
Against Haiku 5.5's documented shifts (output format, early stop at `low`, verification wording)
nothing in either body needs adding or removing.

## Not flagged, with reason

- `subagent-brief.md`, `chain-merge.md`, `ship.md`, `bash-discipline.md`: long, but the long parts are
  fragile operations with exact scripts (keep-list 3), prohibitions with a recorded reason (5), or
  context only the author has (1).
- `diagnose`: numbered phases with a "done when" per phase. Order matters, so the choreography is
  kept (1c exception). `[DEBUG-xxxx]` coupling to `ship.md` is a live cross-file pointer, not a fossil.
- `codify-learnings`, `checkpoint`, `right-model`, `spec-to-pr-retro`: no pattern from a pattern
  group matched beyond L6.
- `output-styles/COPILOT.md`: 239 words, clean.
- `instruction-files.md:14` pins "2.1.277" as the Claude Code version before which `AGENTS.md` is not
  read. A version pin, with its source named; left alone (not contradicted).

No tests, scripts or manifests reference the exact text of the lines in the hunks that I could find
by grep for the quoted strings in `plugin-tests/`, except that `test_skill_lint.py` fails on bare
`references/` pointers and unresolved paths (none of the hunks adds one). Before applying A3 and A4,
grep `plugin-tests/` for the old strings; I did not.
