---
name: project-review
description: "CTO-level review of this repo — assesses vision, structure, requirements, architecture, and validation across the whole codebase (read the project-context overlay for this repo's workspace shape). Triggers on /cla:project-review or natural language like 'review the whole project', 'CTO-level review', 'assess the codebase'."
allowed-tools: Read, Bash, Grep, Glob, Agent
---

# Project Review

Run a comprehensive CTO-level review of this repo (see the project overlay for what it is). Spine: **Step 0 mechanical checks (run FIRST) → Step 1 snapshot → Step 2 five parallel review agents → Step 3 aggregate, report, log.**

**When to run:** After several incremental changes, before a pitch/demo, or when you want a fresh first-principles assessment.

**Run thin (standing discipline — hoisted).** This skill IS an orchestrator: Step 2 dispatches five parallel review agents and Step 3 aggregates only their conclusions, never their raw reads. Follow `.claude/plugins/cla/skills/spec-to-pr/references/runtime-rules.md`'s standing disciplines throughout — delegate raw-material handling so only conclusions return, read file slices not whole files, batch independent tool calls into one message, and prefer terse schema'd agent output over prose.

## What the repo is (read before reviewing)

**Read the project overlay `references/project-context.md` ("What the repo is") before reviewing** — it describes what's specific to this repo's project-review pass. It's this repo's overlay (the fixed `project-context.md` filename, preserved across `update-cla` syncs by convention); a repo adopting `cla` swaps it for its own. For the repo-wide facts (workspace layout, backend, mock-dataset location, i18n layers, dev/build/test commands), also read `cla.io/project-facts.md` (run `/cla:sync-context` to populate it; falls back to the overlay if absent). The per-dimension agent prompts below, and the Step-1 Project Snapshot template, source their repo facts from these two sources via orchestrator injection at dispatch time (`references/project-context.md` — "Per-dimension agent-dispatch injection facts"; `cla.io/project-facts.md` for the shared facts) rather than hardcoding them. When naming a product/domain concept in the report, prefer this repo's canonical term from `cla.io/terminology.md` if it exists and covers the concept (soft — proceed on your own judgement if absent or silent on the term).

## Step 0: Mechanical checks — run FIRST, before any agent dispatch

This step MUST complete before Step 2's dispatch — every agent receives its output as pre-verified input. **Read `references/mechanical-checks.md` first** for the full checklist: what each check means, where its exact commands live (`cla.io/project-facts.md` / the project overlay), and how to interpret PASS/FAIL/SKIP. This stub carries only the ordering invariant and the one command worth having on hand:

```bash
node .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.mjs
```

Print any FAIL immediately (`[Project Review] ⚠ {check}: {details}`), then collect everything into the **Mechanical Facts** table (format in the reference). Announce: `[Project Review] Mechanical checks complete — {n} PASS, {m} FAIL`

## Step 1: Collect project snapshot

Build a compact **Project Snapshot** that, together with the Mechanical Facts table, is the complete brief every agent receives — do NOT read full file contents to paste into agent prompts; agents read specific files themselves. **Read `references/aggregate-and-log.md` first** for the full snapshot template and its `cla.io/project-facts.md`/overlay sourcing.

Announce: `[Project Review] Launching 5 review agents...`

## Step 2: Launch five review agents in parallel

**Dispatch all FIVE agents concurrently, in a single message, via the Agent tool** (`general-purpose` unless a more specific agent fits) — this is the core dispatch invariant of this step; do not stagger or sequence them. **Read `references/review-agents.md` first** for the full prompt text (the standard instructions every agent gets, plus each of the five dimension-specific prompts) and construct each agent's prompt from it before dispatching. Read `references/review-criteria.md` for the grading rubric. Each agent receives: (1) the Project Snapshot, (2) the Mechanical Facts table, (3) the relevant dimension criteria, (4) the standard instructions from the reference.

**Model routing (pass an explicit `model:` per agent) — per the shared `.claude/plugins/cla/skills/spec-to-pr/references/model-routing.md` "Review-agent dispatch" section:**
- **Agent 1 (Vision & Clarity) and Agent 4 (Architecture & Design) → `model: "opus"`** — the two premise-level dimensions (does the product story hold; is the architecture sound), where a cheaper model's miss is the expensive "the whole design is wrong" class.
- **Agents 2, 3, 5 (Structure, Requirements & Specs, Validation & QA) → `model: "sonnet"`** — structured-rubric application over layout/specs/tests, where sonnet is sufficient.

Effort is not dialable on `Agent`-dispatched work (it inherits the session); only the model is set here. On a session already at Opus, routing Agents 2/3/5 down to sonnet is the real economy; on a sub-Opus session, routing Agents 1/4 up to opus protects the highest-leverage judgment. Apply the routing whenever the session model differs from a dimension's target tier.

## Step 3: Aggregate, report, and log

Wait for all five agents, then deduplicate/merge/extract-recommendations and print the report per the recipe in `references/aggregate-and-log.md` — **read that reference first**; this stub carries only the verdict rubric (the one correctness-gating piece of Step 3):

**Compute verdict from dimension grades:**
| Verdict | Criteria |
|---------|----------|
| **EXEMPLARY** | All dimensions A or B, none below B |
| **STRONG** | Majority A/B, at most one C, no D |
| **SOLID** | Majority B/C, no more than one D |
| **NEEDS WORK** | Two or more D grades, or majority C/D |

The report is the whole output — this skill persists no state across runs.

## References

- `references/mechanical-checks.md` — Step 0's full checklist: what each check verifies, exact commands, PASS/FAIL/SKIP interpretation, and the Mechanical Facts table format (mandatory-read from the Step 0 stub)
- `references/review-agents.md` — Step 2's full per-agent dispatch prompts: the standard instructions plus all five dimension prompts (mandatory-read from the Step 2 stub)
- `references/review-criteria.md` — the portable grading rubric (signals + grade definitions) per dimension
- `references/aggregate-and-log.md` — Step 1's snapshot template plus Step 3's dedup/merge/report-template/retro-log-append recipe (mandatory-read from the Step 1 and Step 3 stubs)
- `references/project-context.md` — this repo's project overlay: what the repo is, per-dimension agent-dispatch injection facts, and the mechanical-check/review-criteria repo specifics (read by the orchestrator at dispatch time; dispatched agents never load it themselves)
- `.claude/plugins/cla/skills/spec-to-pr/references/model-routing.md` — the shared model/effort routing table (Step 2's "Review-agent dispatch" section is the single source of truth for this skill's per-agent model)
- `.claude/plugins/cla/skills/spec-to-pr/references/runtime-rules.md` — the thin-orchestrator standing disciplines this skill follows (delegation, I/O hygiene, batching, structured output)
