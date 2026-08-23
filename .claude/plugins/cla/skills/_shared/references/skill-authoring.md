# Skill-authoring doctrine (plugin-wide)

This is plugin-wide doctrine: it lives in `_shared/` because every skill is held to it, not because any one skill owns it. `spec-to-pr` is the largest worked example — its `references/{ship,revise,archive,handoff}.md` show the split in practice.

## The transformation, in order

1. **Baseline.** `wc -w -c <skill>/SKILL.md` — record before.
2. **Classify every section** as INLINE-invariant (stays) or MECHANICS (moves) — see the boundary below.
3. **Move mechanics** into on-demand `references/*.md` (per-phase or per-topic; reuse existing reference files, don't duplicate). Each moved section leaves a **short inline stub** = the load-bearing one-liner(s) + a mandatory **"read `references/<name>.md` first"** pointer.
4. **Route repo-specific worked examples** (real symbol/file names, dated incidents) that you move OUT to the skill's `cla.io/overlays/spec-to-pr.md` overlay, leaving a generic pointer in the synced-core reference — per the **Skill fact/procedure separation** requirement. Never let a repo token land in a generic synced-core `references/*.md`.
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

- **`git_state`-before-every-commit** — the #1 repeat offender: it commonly lives in phase-step prose rather than the hoisted block, so the restructure silently drops it from the inline stub (caught only by review when that happens — see `cla.io/overlays/spec-to-pr.md` "Incident history" for concrete precedents). If the skill runs its own commits, this MUST be a hoisted one-liner, not left only in the moved recipe.
- **never `git add -A` / path-scoped staging.**
- The skill's **merge / quarantine / halt authorization** (e.g. multi-pr's whole-chain-halt vs multi-lite's downstream-only quarantine — these differ per skill; preserve the SKILL's own semantics verbatim, never swap in a sibling's).
- Any **safety-confirmation gate** (e.g. codify-learnings' interactive-apply confirmation; spec-to-pr's destructive-git ask).
- Push-verification, exit-gate, and no-unresolved-finding rules.

## Validation (before shipping)

- **`wc -w -c` after** — note before/after. The ~size target is **aspirational, not a gate**: correctness prose staying inline WINS over hitting a number. Never relocate an invariant to shrink the file (the `wc` proxy is gameable exactly this way — the "invariants stay inline" spec scenario is the guard).
- **Conformance guard** — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/check_no_project_tokens.py` MUST **exit 0** (no repo token, and no hardcoded absolute developer path, leaked into a new synced-core reference). It is a program, not a pytest module: a consuming repo has no test gate over the plugin cache.
- **Pointer resolution** — every mandatory-read pointer resolves to a real file; a cross-skill pointer (e.g. `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`) uses the full path.
- **A behavior-preservation read** — diff removed-vs-retained lines and confirm no correctness-gating invariant left inline context and each stub is self-sufficient.

## Completion criteria — every step says how the agent knows it is done

A step an agent cannot self-check is a step it will report complete while
half-done. Progressive disclosure decides *where* an instruction lives; this
decides whether the instruction is finishable.

For each numbered step or phase you write, the reader must be able to answer
"am I done?" from the step itself — with a check, not a feeling:

- ❌ "Review the affected files." → done is unobservable; any amount qualifies.
- ✅ "Review every file the Impact section names; each one gets a verdict line
  in the report." → done is countable against a list.
- ❌ "Make sure the tests still pass." → which tests, and what proves it?
- ✅ "`run_tests.py` exits 0 with no near-miss warning." → one command, one bit.

Two shapes that satisfy this cheaply: name the artifact the step must produce
(a row, a commit, a file), or name the command whose exit code settles it. A
step with neither is prose, and prose does not finish.

This pairs with the plugin's grounding contract — a claim resolves to verbatim
evidence or an explicit NOT-FOUND. Completion criteria are the same discipline
applied to *work* rather than to *claims*: both replace "it seemed fine" with
something falsifiable.

## Prove it adjacent — a claim about the repo carries the command that settles it

Completion criteria make *work* checkable. This makes *claims* checkable, and it
exists because the failure is common, cheap to prevent, and expensive to catch.

When prose in this plugin asserts a fact about the repo's own state — a count, a
"measured", a "zero", an "always"/"never", a "nothing else does X" — put the
command that proves it on the next line:

```
# 99 files scanned, 36 using the placeholder (python -c "…_scanned_files()…")
```

Three reasons this is a rule and not a preference:

1. **The claims that are wrong are the ones nobody could re-run.** Every false
   assertion caught in this repo's reviews was falsifiable by a single command
   the author never ran — "widening the roots fails on the fixtures" (it yields
   zero violations), "deleting the skill changes the floors" (it changes them by
   zero). Writing the command is what turns an intuition into a measurement.
2. **A number without its command rots silently.** `lib/log_run.py` carried
   "132 records" against an actual 0 for months; a docstring stating a count is
   a fact with no guard. Either quote the command, or do not quote the number.
3. **One comment can falsify itself.** A note claiming "no repo token appears
   in these files" that itself contains the token is not a hypothetical — it
   shipped here. Re-running the adjacent command after the edit catches it; the
   claim alone never will.

The counter-rule, so this does not become decoration: **if the claim needs no
command, it needs no comment.** "This list is hand-typed on purpose" is a design
statement, not a measurement, and adding a fake command to it is worse than
nothing.
