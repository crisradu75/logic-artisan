# Token diet — spec-to-pr briefs (2026-10-11)

Source: `cla.io/decisions/token-diet-program-2026-10-11.md` (decisions are final). These are the two
spec-bound items (decision 12). Start each with `/cla:spec-to-pr` in its own session, **brief 1
first**: brief 2's rules text carries the review table brief 1 creates, so it must not invent a
second copy. Run them one at a time (decision 13: one PR at a time per area).

## Brief 1 — Risk-sized review (decisions 4, 5)

**Change.** The agent judges each PR's risk from its diff and writes one line in the PR body (risk
level, reason, reviewers chosen). One table in `model-routing.md` sizes the review: low-risk docs get
`comment-analyzer` on Sonnet; low-risk code gets `code-reviewer` on Sonnet; high risk gets
`code-reviewer` + `silent-failure-hunter` on Opus. A second review round runs only after a Critical
finding was fixed. Risk signals (generic): writes or deletes of files or data, money or scoring,
auth or secrets, guard hooks and checkers, concurrency, and changes to agent instructions (skills,
prompts, agent definitions). Unsure means high. A prose-dominant diff (the mechanical count at
`revise.md:25`) is high risk and keeps the Opus `plugin-dev:skill-reviewer` alongside the
bug-hunters. `spec-to-pr`, `lite-pr` and the chains cite the table.

**Orchestration-skill rules (decision 13).** `multi-pr`, `multi-lite` and `multi-spec` each carry,
by citing one shared reference and not by copying it: an explicit `model:` on every `Agent`
dispatch; complete first briefs with reports of about 300 words; touched tests while iterating, the
full suite once on the final commit, the orchestrator re-verifying that commit; one PR at a time
per area; a handoff file when the orchestrating chat grows long; high-risk implementers on Opus;
the debris check as one command in the Test phase (nothing created outside the test framework's
temp dir). Brief 2's rules file cites the same reference, so the text lives once.

**Spec amended.** `openspec/specs/change-workflow/spec.md:11` (second review "unless `--pr-rounds`
allows only one round", i.e. round 2 whenever round 1 committed fixes) and scenario `:19-22`.
Rewrite as MODIFIED-via-REMOVED+ADDED per `openspec/config.yaml:24`.

**Never-demote wording to retire (all of them):** `revise.md:31`, `revise.md:33`,
`model-routing.md:46`, `model-routing.md:133-145` (the phantom-finding section, `:67` also states
it), `spec-to-pr-retro/SKILL.md:27`, and `lite-pr/SKILL.md:148` (its reviewer selection). Also
`revise.md:5` (round-2 trigger).

**Acceptance.**
- A low-risk code diff dispatches one Sonnet `code-reviewer`; a signal-matching diff dispatches both
  bug-hunters on Opus; the PR body carries the risk line.
- Round 2 does not run after a round 1 that fixed only Important or lesser findings; it does after a
  fixed Critical.
- `grep -rn "never demoted\|Never demote" .claude/plugins/cla` finds no surviving claim that
  contradicts the table.
- `openspec validate --specs --strict` passes; the pytest gate passes.

**Files likely touched.** `model-routing.md`, `spec-to-pr/references/revise.md`,
`spec-to-pr/SKILL.md`, `lite-pr/SKILL.md`, `spec-to-pr-retro/SKILL.md`, `multi-pr`, `multi-lite`
and `multi-spec` (their SKILL.md plus the references that name review rounds), the shared
economy reference, the `change-workflow` spec, and any test pinning round-2 wording.

## Brief 2 — Consumer economy rules file (decisions 2, 13, 6's dispatch rule)

**Change.** `/cla:cla-setup` writes `.claude/rules/cla-economy.md` in the consuming repo, owns it
whole and replaces it on every run; the repo's `CLAUDE.md` is untouched. The text lives once in the
plugin as a shared reference that CLA skills cite. Content, worded for any repo: model by task
(cheap model for sweeps and mechanical work, Sonnet default for authoring and fixes, Opus only
where judgement carries risk; pass `model:` on every dispatch); the review table and risk call from
brief 1; complete first briefs with reports of about 300 words; touched tests while iterating, the
full suite once on the final commit, the orchestrator re-verifying that commit; one PR at a time per
area; a handoff file when the orchestrating chat grows long; high-risk implementers on Opus; the
quality floor (claims cite file:line, protected rules never dropped, real-file check on copies,
debris check, owner-approved before/after for score- or gate-moving changes, cleanup after one
`[y/n]`).

**Spec amended.** `openspec/specs/repo-context/spec.md:100` ("changes no existing file except ...
`.gitignore`"): `cla-setup` owns exactly this one file and replaces it whole. Check
`openspec/specs/plugin-distribution/spec.md:35` ("repo data stays in the repo") against the same
change.

**Acceptance.**
- Running `/cla:cla-setup` in a repo with no such file creates it; with an edited copy, replaces it
  and says so; no other existing file changes besides the `.gitignore` append.
- `python3 .claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py` passes on the
  shipped text.
- The seeded rules and `config.yaml` tests still agree.

**Files likely touched.** a new shared reference under `skills/_shared/references/`,
`skills/cla-setup/SKILL.md`, the two specs, cla-setup tests, and the skills that cite it.
Version impact: at least a minor bump; release only on explicit owner approval.
