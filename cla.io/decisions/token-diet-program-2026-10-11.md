# Token diet program — decisions (2026-10-11)

**Topic:** every open suggestion in the token-diet issues — #296 (P0, what every change run
reads), #297 (P1, streamlined cycle), #299 (P3, dedupe) — plus #322 (the "operate economically"
policy for multi-agent batches). #298 (P2, always-on context) is closed and was not re-proposed.

**Goal:** fewer tokens in this repo's own work, and in every repo that installs CLA — including
agent work done outside CLA skills.

**State at decision time** (`python3 plugin-tests/scripts/measure_load.py` on `main` at `86e00c5`):
session load 1,222 words; `spec-to-pr` typical run 18,711 words (from 47,146); `lite-pr` 4,744;
`review-change` 5,618. `cla.io/lessons-learned/lessons-learned.md` is 13,016 words (`wc -w`).
#322's evidence (crisradu75/claude-plugins#511): 100k–850k tokens per agent, most PRs 2–3 review
rounds, every author and implementer on Opus.

## Decisions

1. **What comes first:** #322's batch policy first, with the overlapping trims folded in
   (#296 item 5 = #322 item 1; #297 item 6 overlaps #322 item 2); the rest after. **Plus:** CLA
   writes the economy guidance into consumer repos, so it governs agent work outside CLA skills.
   — Targets the largest measured cost and reaches consumers.
2. **Delivery to consumers:** `cla-setup` writes `.claude/rules/cla-economy.md`, a file CLA owns
   whole and replaces on each run; the consumer's `CLAUDE.md` is untouched (optional one-line
   mention). The text lives once in the plugin as a shared reference that CLA skills cite.
   — Verified at code.claude.com/docs/en/memory: "Rules without `paths` frontmatter are loaded at
   launch with the same priority as `.claude/CLAUDE.md`." Clean ownership, no merging into the
   owner's prose. **Spec-bound (decided after review):** amend `repo-context/spec.md:100`
   ("changes no existing file except … `.gitignore`") so `cla-setup` owns exactly this one file
   and replaces it whole; check `plugin-distribution/spec.md:35` in the same change.
3. **Who decides high risk:** the agent, per PR, from the diff. No per-repo risk list.
   — No setup per repo.
4. **How the risk call is made:** one line in the PR body (risk level, reason, reviewers chosen),
   guided by a generic signal list in the plugin (writes or deletes of files or data, money or
   scoring, auth or secrets, guard hooks and checkers, concurrency, and **changes to agent
   instructions: skills, prompts, agent definitions**). Tie-break: unsure → high risk. A
   prose-dominant diff (`revise.md:25`'s mechanical count) is high risk and keeps the Opus
   `plugin-dev:skill-reviewer` on top of the bug-hunters (decided after review).
   — Auditable by grepping PR bodies; doubt fails safe.
5. **Review sizing:** one table in `model-routing.md`, cited by `spec-to-pr`, `lite-pr`, the
   chains and the rules file. Low-risk docs → `comment-analyzer` on Sonnet. Low-risk code →
   `code-reviewer` on Sonnet. High risk → `code-reviewer` + `silent-failure-hunter` on Opus.
   Round 2 only after a Critical fix (today: whenever round 1 committed fixes, `revise.md:5`).
   — Cheapest; one rule everywhere. Accepted risk: a misjudged "low" gets fewer reviewers AND a
   weaker model, and with decision 6 the risk call and Revise triage (`model-routing.md:130`,
   never escalated) are both Sonnet, so such a PR never touches Opus and Sonnet alone decides
   "Critical", which is what triggers round 2. Retires "never demoted, in ANY round" at every
   site: `revise.md:31`, `revise.md:33`, `model-routing.md:46`, `model-routing.md:133-145`,
   `spec-to-pr-retro/SKILL.md:27`, `lite-pr/SKILL.md:148`. **Spec-bound:**
   `change-workflow/spec.md:11` and its scenario `:19-22` require round 2 whenever round 1
   commits fixes.
6. **Orchestrator model:** Sonnet session by default (including this repo's `cla` launcher);
   escalate-up to Opus for Propose authoring and for seconding a Review verdict on the
   FIX FIRST / RETHINK line (`model-routing.md:115-129`, `:125-127`);
   `model:` required on every dispatch as a prose rule, no hook.
   — Cuts per-turn main-chat cost; a forgotten `model:` inherits Sonnet, the default anyway.
7. **Measurement:** a dev-only transcript meter in `plugin-tests/scripts/`, reading per-message
   `usage` from session transcripts (main chat and `subagents/`), split by model. Run before and
   after, in this repo and one consumer repo. Nothing ships.
   — Verified: transcripts record model, input, cache-read, cache-write and output tokens per
   assistant message. Caveat: the transcript format is not a public contract.
8. **Tiny tier (#297 item 6):** no new tier, no size check. Lazy-load three `lite-pr` blocks
   behind one-line triggers: `Measured-by` rules, the mutation gate, the diagnose escalation.
   Every rule moves verbatim. — A size gate inside `lite-pr` changes nothing (the workflow was
   already chosen); risk sizing covers big diffs at review.
9. **Mechanical phases (#296 item 4):** commands first, phase by phase (e.g. `gh pr checks
   --watch`, `gh pr merge --match-head-commit`, `openspec archive`). A script only where a
   command plus one sentence demonstrably fails, citing the failure.
   — Follows the lean-plugin rule; Sonnet orchestration lowers the value of each avoided turn.
10. **Artifact caps and tasks (#297 item 8, absorbs #175):** caps (task ≤ ~40 words, design
    ≤ ~800, proposal ≤ ~400), and each task states one behaviour with a testable acceptance
    criterion, no file:line. Set at authoring through the `config.yaml` rules `cla-setup` seeds;
    checked as findings in the existing `review-change` checklist. Applies to every `tasks.md`.
    Already in place, not new: no reasons in specs (`openspec/config.yaml:23`), MODIFIED →
    REMOVED + ADDED (`:24`), "cite headings, not line numbers" (`:29`), length rules on MODIFIED
    blocks (`checklist.md:66`); #297's "MODIFIED is exempt" premise is stale and there is no
    `rationale.md` anywhere. Edit `cla-setup/SKILL.md:128` and `config.yaml` in one commit
    (`test_cla_setup_rules_match_config.py`). The line-drift check at `checklist.md:50` becomes
    a "task names a line" finding.
    — Authoring rules drift (proposals reached 1,971 words); the review check costs a line.
11. **The rest, only what is still open:** archive old lessons-log entries (the log is already
    searched, not read whole, `codify-learnings/SKILL.md:40`, with entries prepended at ≤150
    words, `:96`); #296 item 3b (fixed reviewer agents with `model:` and read-only tools; only
    `doc-sweeper` and `fact-gatherer` exist); `check_fact_paths.py` skips machine-local paths
    (`_keep_if_path` has no `*.local.*` rule). **Already done before this decision:**
    `codify-retro` deleted (`bb691f3`), so no retro merge is left; the `lite-pr`,
    `shape-decision`, `feedback` run logs are retired (`log_run.py:15`,
    `test_cla_setup_retired_ledgers.py:29-31`); the old run-log rule is gone. Also done: #296
    item 1 (#293 closed, live specs 6,497 words) and item 2 (`spec-to-pr` SKILL.md 4,318 words).
13. **The rest of #322, all adopted, worded for any repo** (decided after review), in the rules
    file and the orchestration skills: complete first briefs with reports of about 300 words;
    touched tests while iterating, the full suite once on the final commit, the orchestrator
    re-verifying that commit; one PR at a time per area; a handoff file when the orchestrating
    chat grows long; high-risk implementers (decision 4's signals) on Opus; the quality floor —
    claims cite file:line, protected rules never dropped, real-file check on copies, debris check
    ("nothing created outside the test framework's temp dir", one command in the Test phase, no
    script), owner-approved before/after for score- or gate-moving changes, cleanup after one
    `[y/n]`. #297 item 8b's out-of-scope note per task: optional, where it helps.
12. **Delivery:** a plan built from this file. Items that change a live spec requirement →
    `spec-to-pr`; the rest → a `multi-lite` chain, in a separate session the owner starts.
    — Cheaper than OpenSpec for everything; spec changes still get a reviewed delta.

## Decision summary

| # | Question | Choice |
|---|---|---|
| 1 | What first | #322 policy first, overlaps folded in; plus consumer guidance outside skills |
| 2 | Consumer delivery | `cla-setup` writes `.claude/rules/cla-economy.md` (CLA-owned) |
| 3 | Who decides risk | Agent, per PR, from the diff |
| 4 | Risk call | One PR-body line + generic signals; unsure → high |
| 5 | Review sizing | One table; low risk → one Sonnet reviewer; high → both bug-hunters on Opus; round 2 only after Critical |
| 6 | Orchestrator | Sonnet + escalate-up; explicit `model:` as prose |
| 7 | Measurement | Dev-only transcript meter |
| 8 | Tiny tier | No tier; lazy-load three `lite-pr` blocks |
| 9 | Mechanical phases | Commands first; scripts only on proven failure |
| 10 | Caps and tasks | Caps + behaviour tasks; authoring + existing review |
| 11 | The rest | Only what is still open: lessons-log archiving, reviewer agents, local-path skip |
| 12 | Delivery | Plan → spec-bound (2, 5) to `spec-to-pr`, rest to `multi-lite` |
| 13 | Rest of #322 | All adopted, generic wording; quality floor included |

## Open before execution

- **Build the transcript meter first**, so a "before" baseline exists for every token claim.
- **Verify escalate-up fires on a Sonnet session**; it is the economy policy's first task.
- **Spec-bound items** (independent review against the 8 live capabilities): decision 5
  (`change-workflow/spec.md:11`, `:19-22`) and decision 2 (`repo-context/spec.md:100`, also
  `plugin-distribution/spec.md:35`) → `spec-to-pr`; arguably the `check_fact_paths.py` skip
  (`repo-context/spec.md:20`). Everything else → `multi-lite`.
- **Guard tests:** none pins the never-demoted wording; `test_mutation_gate_sites_agree.py`
  finds the mutation gate by text in any `.md`, so a verbatim move passes.
- **Release:** adding the rules file and changing review behaviour is at least a minor version;
  cut only after review, with explicit approval.

**Why it matters / next step:** the per-skill read cost is mostly already cut; the remaining
spend is in orchestration (models, review rounds, main-chat length), in this repo and in
consumers. Next: draft the plan that routes items 1–12 into a `spec-to-pr` set and a
`multi-lite` decisions file, then the owner starts the chain in a separate session.
