# Spec level and style — what a spec says, and how much

Written 2026-10-08, the third doc of the simplification program, alongside
`retro-and-learning-loop-simplification-2026-10-08.md` and
`plugin-surface-simplification-2026-10-08.md` (same PR). Shaped with the owner question by
question the same day.

**The concern that started it.** The live specs in every repo are too detailed and hard to read.
CLA over-specifies: it writes implementation choices and its own skill mechanics into specs
instead of stating outcomes and trusting the model to turn them into code. The 2026-10-07
rewrite of this repo's specs shortened the text but did not change that level, so no existing
spec is treated as a model here.

---

## Grounding

Read-only investigation over `logic-artisan` (`4b8f50c`), `interoga-ro` (`98a9b909`),
`claude-plugins` (`096800d`) and `market-distiller-mcp` (`53d3b4d`), with OpenSpec 1.14.1.
Scratch scripts, stdlib only: `specstats.py` (per-spec counts and a Flesch reading-ease
estimate), `deltas.py` (archived deltas before and after a date), `levels.py` (a keyword level
classifier with seeded random sampling for hand labelling). Shares marked "estimate" come from
small samples.

**The limit is 500 characters, not words.** OpenSpec's `MAX_REQUIREMENT_TEXT_LENGTH = 500`
(`dist/core/validation/constants.js:9`) warns "Requirement text is very long (>500
characters)" — about 75–90 words, requirement text only. CLA's `openspec/config.yaml` rule says
the same.

**Size today** (`specstats.py`; over-limit count from `openspec validate --specs --strict | grep -c 'very long'`):

| repo | requirements | words per requirement (median / max) | over 500 characters | scenarios per requirement (mean / max) |
|---|---|---|---|---|
| logic-artisan | 73 | 75 / 386 | 35 | 3.1 / 12 |
| interoga-ro | 707 | 174 / 4,269 | 535 | 4.9 / 45 |
| claude-plugins | 553 | 102 / 1,426 | 348 | 4.1 / 35 |
| market-distiller-mcp | 372 | 63 / 949 | 173 | 2.9 / 19 |

1,091 of 1,705 live requirements (64%) exceed OpenSpec's own limit.

**Level** (hand-labelled random sample of 8 requirements per repo, seed 7 — estimate):

| repo | user-facing outcome | true interface | implementation detail | skill internals |
|---|---|---|---|---|
| logic-artisan | 0 | 0 | 1 | 7 |
| interoga-ro | 5 | 0 | 3 | 0 |
| claude-plugins | 2 | 1 | 5 | 0 |
| market-distiller-mcp | 0 | 4 | 4 | 0 |

By keyword count, 59 of logic-artisan's 73 live requirements name a skill, agent, finding or
review round. Example of the anti-pattern: `change-authoring/spec.md:33`, "The multi-spec
authoring brief SHALL state OpenSpec's stock limits in one line" — a rule about how a skill file
is worded, which `config.yaml`'s own `skip_specs` rule says is not spec material.

**What pushes specs toward detail:**

1. This repo turns rules learned from incidents into SHALL requirements about its own skills.
2. review-change treats code names in specs as normal (`checklist.md:42`, `dispatch.md:108`),
   checks each SHALL against current code (`dispatch.md:105`), lists "pinning a wording detail"
   as a fix (`checklist.md:201`), and asks for the delta spec when a later change depends on a
   field (`checklist.md:124`).
3. spec-to-pr Review applies every Critical and Important finding by editing the change's
   files, so fixes land as spec text (`spec-to-pr/SKILL.md:168`).
4. Edited requirements only grow. MODIFIED requirements in archived deltas are 2–2.8× the words
   of ADDED ones in every repo (`deltas.py`). review-change exempts them from the length check
   (`checklist.md:65`), and live specs are validated without `--strict`, which silences
   OpenSpec's length warning (`archive.md:31`, `lite-pr/SKILL.md:54`,
   `multi-pr/references/change-loop.md:85`).
5. lite-pr edits live specs directly, with no delta and no rules ("plain prose … is fine",
   `lite-pr/SKILL.md:46`).
6. The scenario-to-test proof rule (added 2026-10-07 here and in interoga-ro) makes every new or
   changed scenario carry its own test, which rewards narrow, unit-test-shaped scenarios.
7. The rules reach consumers inconsistently: `cla-init` writes `rules:` only when no
   `openspec/config.yaml` exists. claude-plugins and market-distiller-mcp have no `rules:`
   block; interoga-ro has its own without the plain-words rule. Copies of the rule also sit in
   multi-spec's authoring brief, spec-to-pr and review-change.

**The 2026-10-07 rule works for new text.** Requirements in this repo's deltas archived since
then average 57 words, against 391 before (`deltas.py logic-artisan 2026-10-07`).

## Decisions (all agreed with the owner, 2026-10-08)

- **S1 — A spec states outcomes and true interfaces only.** An outcome is something a user or
  owner would recognise. An interface is something others depend on: a CLI flag, a file or
  ledger format a consumer reads, an API contract. Implementation choices are left to the
  model; a detail a reviewer must agree on (a security parameter, a data model) goes in
  design.md. How CLA's skills and agents work internally stays in SKILL.md and is never spec
  material.
- **S2 — Size limits.**
  - Each requirement is one sentence within OpenSpec's 500-character limit, enforced by
    `openspec validate --strict` — no new script.
  - At most 3 scenarios per requirement and 8 requirements per capability.
  - The limits apply to edited (MODIFIED) requirements too: the exemption in review-change and
    the three non-`--strict` validation carve-outs go.
- **S3 — Prove requirements, not scenarios.** Each outcome or interface requirement needs at
  least one test, or a `manual:` line with a reason. Scenarios are examples, not test
  contracts. The `config.yaml` tasks rule, `cla-init`'s copy, review-change and
  `test_scenario_proof_format.py` change to match; interoga-ro's guard is adjusted when that
  repo next takes the rules.
- **S4 — Invert the review rules that push detail into specs.**
  - A code name, file path or skill-internal rule in a spec becomes a finding.
  - Review fixes go to design.md, tasks or code; into spec text only when the finding is about
    an outcome or interface.
  - Delete "pin a wording detail" as a fix and the delta-spec ask for cross-change fields.
- **S5 — `openspec/config.yaml` `rules:` is the single source.** OpenSpec injects it into
  authoring. Skills say "apply config `rules.specs`" instead of carrying copies (multi-spec's
  brief, spec-to-pr, review-change). `cla-setup` reports missing or outdated rules in an
  existing config and offers to update them.
- **S6 — lite-pr edits a live spec only to change an outcome or interface,** applying config
  `rules.specs` and validating with `--strict`.
- **S7 — Rewrite logic-artisan's live specs now; consumers adopt going forward.**
  - logic-artisan: one rewrite change (REMOVED + ADDED, `--strict` as the gate) to the S1/S2
    level. Skill-internal requirements are deleted from the specs (their rules already live in
    SKILL.md and tests). Every dropped scenario is named in the change. Estimate, from a small
    sample: about 18.6k words down to roughly 1–2k.
  - Consumers keep their specs. New and edited requirements meet the new level once each repo
    takes the rules (via `cla-setup`'s report).
  - **Consequence to watch:** because S2 holds edited requirements to the limit, the first
    change that touches a large consumer requirement must rewrite it — for example interoga-ro
    `data-persistence/spec.md:95` (4,269 words). Expect some small changes there to carry a
    rewrite.

## Delivery

- **Same PR** as the other two docs.
- **Order:** after the plugin-surface doc's P5 (guard layer), and **before** both other chains:
  1. The rule changes: S1–S6 across `openspec/config.yaml`, `cla-init`/`cla-setup`,
     multi-spec's brief, spec-to-pr Review, review-change, lite-pr,
     `test_scenario_proof_format.py`, the `scenario:` comments in this repo's tests (12, in 4
     files, `grep -rh "# scenario:" plugin-tests/tests | wc -l`).
  2. The S7 rewrite of logic-artisan's six live specs.

  Every later change in the program is then authored at the new level.
- **Release:** part of 2.0.0.
