## Why

`review-change/references/checklist.md` states a Grounding contract (line 68): every claim resolves
to verbatim evidence or an explicit NOT-FOUND. Five open issues report failures under it, and four
of them (#124, #126, #118, #119) share one mechanism — the reviewer **had** the rule and did not
recognise the sentence in front of them as a claim, because it was phrased as an explanation, a
comparison, a requirement, or a trade rather than as an assertion about existing code. #119 says so
in the reporter's own words: "I approved a compensation I did not verify... the check is one grep."

That is a recognition failure, not a procedure failure, and the four issues each propose the same
remedy — one more numbered check in a file that already carries 0a–0k. The fifth issue (#109) is a
different thing entirely: a tie-break for when two dispatched reviewers grade one finding
differently.

## What Changes

- **Add a named claim-shape list to the Grounding contract.** Four shapes, each with its own trigger,
  its own resolution procedure (what to read, what to resolve it against, what to record), its own
  failure mode, and a severity floor. The list is stated as open, with the shapes' common signature
  given so a reviewer can recognise a fifth that nobody has filed.
- **Add exactly one numbered check, `0l`**, whose whole content is: sweep the artifacts for the claim
  shapes the Grounding contract names, and resolve each per that contract. This is the run-time
  placement the contract section by itself does not have. The precedent is already in the file: `0f–0i`
  is one line that delegates four checks to the overlay.
- **State that `0l` is not delegable to `fact-gatherer`.** The cost-offload paragraph defaults the
  mechanical portion of `0a–0h` to a haiku sub-agent with no `Bash`. All four shapes require reading a
  mechanism and judging it against another mechanism; none resolves to a pass/fail row.
- **Add a severity tie-break where reviewer reports are reconciled** (Step 6, "Deduplicate findings"):
  when two reports carry the same finding at different severities, the severity comes from the report
  whose evidence for that severity is implementation-level — a source line, a schema, a migration, a
  query — over the report whose evidence is the spec delta or artifact text alone.
- **Update the check enumeration at line 60** so `0l` is named where `0a–0e` and `0j–0k` already are.

Not changed: no existing check is renumbered, no report section gains a line, and the report's
one-screen constraint is untouched — the tie-break annotates an existing finding line rather than
adding one.

## Capabilities

### New Capabilities

None. Both requirements are additions to the existing `cla-plugin` capability.

### Modified Capabilities

None. This change is `## ADDED Requirements` only — no live requirement's text or scenarios change,
so no MODIFIED block is written and nothing can be silently dropped at sync.

- `cla-plugin`: two ADDED requirements — one for the Grounding contract's claim-shape list, one for
  reviewer-report severity reconciliation.

## Impact

**Modified**

- `.claude/plugins/cla/skills/review-change/references/checklist.md` — one new subsection under
  §"Grounding contract", one new numbered check `0l`, one sentence in the cost-offload paragraph, one
  clause at line 60's check enumeration, one paragraph at Step 6's deduplication step.

**New**

- None. No script, no hook, no test fixture; this change is portable prose in synced core.

**Batch coupling**

- `fix-brief-binding-defect` (same PR) edits the **same file**: the cost-offload paragraph's
  adjudication sentence, and the `### Verified claims` report block. This change touches the
  cost-offload paragraph too, with a different sentence, and deliberately does not touch
  `### Verified claims`. Ordering is pinned in `tasks.md`.

**Portability**

- Synced core, so no repo token, no dev-tree path, no absolute developer path may appear in the added
  prose. `_shared/scripts/check_no_project_tokens.py` is the gate.

**Closes**

- GitHub issues #124, #126, #118, #119, #109.
