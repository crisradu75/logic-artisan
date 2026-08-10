# progressive-disclosure — the recipe for conforming a SKILL.md

A plugin-wide authoring recipe (it lives here because `spec-to-pr` is the reference implementation — its `references/{ship,revise,archive,handoff,runtime-rules}.md` + inline stubs are the worked example — but it applies to ANY cla skill). It is the "how" for the `cla-plugin` **Skill token-efficiency disciplines** spec requirement (`openspec/specs/cla-plugin/spec.md`, discipline 1). Read it before progressive-disclosing a skill so the keep-inline/move boundary isn't re-derived from scratch each time.

## The transformation, in order

1. **Baseline.** `wc -w -c <skill>/SKILL.md` — record before.
2. **Classify every section** as INLINE-invariant (stays) or MECHANICS (moves) — see the boundary below.
3. **Move mechanics** into on-demand `references/*.md` (per-phase or per-topic; reuse existing reference files, don't duplicate). Each moved section leaves a **short inline stub** = the load-bearing one-liner(s) + a mandatory **"read `references/<name>.md` first"** pointer.
4. **Route repo-specific worked examples** (real symbol/file names, dated incidents) that you move OUT to the skill's `references/project-context.md` overlay, leaving a generic pointer in the synced-core reference — per the **Skill fact/procedure separation** requirement. Never let a repo token land in a generic synced-core `references/*.md`.
5. **Update the `## References` list** for any new file.
6. **Post-size + validate** (see "Validation" below).

## Keep-inline vs move boundary (conservative)

**Rule: correctness-gating invariants stay inline as one-liners; only mechanics/rationale/templates/examples move.** Each stub MUST be **self-sufficient for its own invariant** — carry the rule itself, not just a "read the reference" pointer, so a skipped read never loses protection.

**Always stays inline:**
- The hoisted skill-level rules block.
- Mode/argument detection, the autonomy/halt contract (+ its exceptions), the per-loop caps table.
- The standalone correctness sections (e.g. "Bash-style discipline", "Continue-on-everything", "Development-only boundary") — these do NOT consolidate into a runtime-rules-style reference.
- Per phase: the load-bearing one-liner invariants + the mandatory-read pointer.

**Moves to `references/*.md`:** step-by-step procedures, exact bash/command recipes, snippets, templates, the full option-text of `AskUserQuestion` gates, rationale/tradeoff prose, and worked examples.

## The repeat-offender checklist (what tends to get dropped)

These invariants commonly live in *phase-step prose* rather than the hoisted block, so the restructure silently drops them from the inline stub. **Verify each is still inline after the move:**

- **`git_state`-before-every-commit** — the #1 repeat offender: it commonly lives in phase-step prose rather than the hoisted block, so the restructure silently drops it from the inline stub (caught only by review when that happens — see `references/project-context.md` "Incident history" for concrete precedents). If the skill runs its own commits, this MUST be a hoisted one-liner, not left only in the moved recipe.
- **never `git add -A` / path-scoped staging.**
- The skill's **merge / quarantine / halt authorization** (e.g. multi-pr's whole-chain-halt vs multi-lite's downstream-only quarantine — these differ per skill; preserve the SKILL's own semantics verbatim, never swap in a sibling's).
- Any **safety-confirmation gate** (e.g. codify-learnings' interactive-apply confirmation; update-cla's overlay-preservation + never-auto-merge).
- Push-verification, exit-gate, and no-unresolved-finding rules.

## Validation (before shipping)

- **`wc -w -c` after** — note before/after. The ~size target is **aspirational, not a gate**: correctness prose staying inline WINS over hitting a number. Never relocate an invariant to shrink the file (the `wc` proxy is gameable exactly this way — the "invariants stay inline" spec scenario is the guard).
- **Conformance guard** — `python3 -m pytest .claude/plugins/cla/conformance-checks/tests/test_no_project_tokens.py -q` MUST pass (no repo token leaked into a new synced-core reference).
- **Pointer resolution** — every mandatory-read pointer resolves to a real file; a cross-skill pointer (e.g. `spec-to-pr/references/runtime-rules.md`) uses the full path.
- **A behavior-preservation read** — diff removed-vs-retained lines and confirm no correctness-gating invariant left inline context and each stub is self-sufficient.
