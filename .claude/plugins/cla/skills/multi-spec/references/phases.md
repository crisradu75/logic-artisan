# multi-spec — Phase 1 / 2 / 5 mechanics + the shared push post-check

Full step-by-step procedures for the phases without their own dedicated reference (Phase 3's dispatch mechanics live in `authoring-brief.md`; Phase 4's dispatch + fix-application mechanics live in `review-gate.md`). `SKILL.md`'s phase stubs carry the load-bearing invariants; this file carries the recipes.

## Phase 1 — deriving the change plan

**Primary source: the file's own sequencing/grouping.** Look for a "Sequencing" section (or an equivalently-named ordering decision — `shape-decision` output typically numbers it as the last decision). When present, derive the change list, each change's covered decision numbers, and the dependency order directly from it — **do not** default to one change per numbered decision; the file's own grouping is authoritative (see `references/project-context.md` for a real precedent where amendments folded into existing changes rather than becoming new ones).

**Fallback: derive grouping by judgment.** When no such section exists, read every numbered decision and the Decision Summary table, and group them into coherent, dependency-ordered changes yourself — decisions that share a data model, a component, or an explicit "depends on" relationship belong in one change or in dependency order across changes. This is the same kind of reasoning `multi-pr`'s `discover_sequence.py` automates for already-authored changes via textual heuristics, done here by reading the decisions' content directly since no such script exists for raw decisions text.

**Escalate-up on a sub-Opus session.** This grouping judgment sets every change's scope — on a session below Opus, dispatch it to an `opus` `Agent` (same escalate-up rule `.claude/plugins/cla/skills/spec-to-pr/references/model-routing.md` documents for Propose authoring) rather than deriving it at a lower tier. No-op on an Opus session.

**Output** a change plan — one row per change: kebab-case `name`, the decision numbers it covers, a one-line scope, and `depends_on` (other change names in this batch, if any) — per `references/plan-schema.md`. Print it before authoring starts. Hold it in working context only — do not write/commit it here. Phase 2 persists it once the branch exists, because two of the plan's required fields (`batch_slug`, `branch`) only exist after Phase 2's branch derivation, and a Phase-1 commit would land on `master` (which this skill never pushes), so it wouldn't survive a dead disk anyway.

## Phase 2 — branch preflight + persist the plan

**Branch-slug derivation.** Strip a trailing `-YYYY-MM-DD` from the decisions filename stem (e.g. `payments-provider-migration-2026-08-01.md` → `payments-provider-migration`); if the stem is ambiguous, derive a short kebab-slug from the file's own `# Title` heading instead. Branch name: `docs/propose-<batch-slug>`.

**Preflight (`branch.py` is not reusable here — it hardcodes a `feature/` prefix; use plain git calls):**
1. `git rev-parse --abbrev-ref HEAD` — already on `docs/propose-<batch-slug>` → this is a resume with the upstream already set; skip straight to the persist step below.
2. On `master`: `git rev-parse --verify docs/propose-<batch-slug>` (local) and `git ls-remote --exit-code --heads origin docs/propose-<batch-slug>` (remote). Either existing → resume, `git checkout docs/propose-<batch-slug>`. Neither → `git checkout -b docs/propose-<batch-slug>`.
3. `git_state.py --expect-branch docs/propose-<batch-slug>` before the first commit (branch-name-agnostic, fully reusable).

**Persist the plan, on the branch.** Assemble the plan JSON (Phase 1's grouping plus `batch_slug`/`branch`) per `references/plan-schema.md`, write to `cla.io/decisions/<stem>.multi-spec-plan.json`, then commit and push:
```
python3 .claude/plugins/cla/skills/spec-to-pr/scripts/git_state.py --expect-branch docs/propose-<batch-slug>
python3 .claude/plugins/cla/skills/spec-to-pr/scripts/commit.py --message "docs(openspec): multi-spec plan for <batch-slug>" cla.io/decisions/<stem>.multi-spec-plan.json
git push -u origin docs/propose-<batch-slug>
```
**This is the first push to the new branch, so it MUST set the upstream (`-u`)** — `push.autoSetupRemote` is not assumed set, so a bare `git push` here would fail with "no upstream branch." Every push after this one is bare. On a resume where the branch already existed (steps 1–2 took the checkout path), only write+commit+push the plan here if it's missing — it's normally already committed from the original run.

## Push post-check (shared procedure — Phase 2, every Phase 3 change, Phase 4, the run-log commit)

A push's own 0 exit code is not sufficient evidence a commit reached the remote — a pre-push hook can rewrite/skip the commit and still exit 0; the session can drift onto the wrong branch and push that instead; a detached HEAD can push to a non-PR ref. This skill's entire value proposition is "a pushed commit survives a dead local disk" — an unverified push failure would silently reproduce the exact loss scenario the skill exists to prevent, which is worse than the loss itself because the orchestrator would report success.

After every push named anywhere in this skill:
```
git rev-parse HEAD
git ls-remote origin docs/propose-<batch-slug>
```
Compare the two shas in Claude's own context (do not pipe through `grep`/`awk`). Match → the push genuinely landed, proceed. Mismatch → halt and surface to the user via `AskUserQuestion` — do not silently retry and do not mark the phase done.

## Phase 5 — open the PR

```
gh pr create --title "docs(openspec): <N> <batch-slug> change proposals" --body "Proposals only (all four artifacts each) — not implemented. Changes: <name-1>, <name-2>, .... All pass openspec validate --strict."
```
Single-line body, no `\n#` sequence (same `gh pr create --body` parser-bug avoidance `/cla:spec-to-pr` documents). Post-check: `gh pr view --json url state` returns `OPEN`.

**Resume note:** before creating, check `gh pr list --head docs/propose-<batch-slug> --state open` — if one already exists, skip creation and use it.
