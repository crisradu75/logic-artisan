# Modified-block retention — comparing a delta block against the live requirement

A `## MODIFIED Requirements` block **replaces** the requirement it names rather than patching it, so
a scenario present on the live requirement and absent from the block is deleted when the delta is
applied. The block is internally consistent either way — it carries a full requirement text and a
list of scenarios in both the retaining and the dropping case — so the omission is invisible in the
delta, and only a comparison against the live requirement can see it.

## Procedure

<!-- INJECTABLE: paste verbatim into a dispatch prompt. Stands alone — no forward references. Ends at END. -->

1. Parse `## RENAMED Requirements` in the **same delta file** and build the FROM->TO map.
2. For each `### Requirement: <Name>` under `## MODIFIED Requirements`, resolve `<Name>` through that
   map to the name it carries **in the live spec**, then locate that requirement there.
3. Enumerate `#### Scenario:` headings in the delta's block and in the live requirement's block.
   Block boundary: from the `### Requirement:` line to the next line beginning `### ` or `## `, or
   end of file.
4. Report one line per compared requirement, including a clean one:

   `<capability>/<requirement name>: live N -> delta M (+K added, -J missing)`

   then, only when `K` or `J` is non-zero, one line per differing scenario, heading verbatim:
   `  - <live heading absent from the delta>` / `  + <delta heading absent from the live spec>`

Adjudicate each missing scenario to exactly one of **renamed**, **intentionally removed**, or
**dropped**. Only `dropped` is a finding, and it is **Critical** — it deletes a live `SHALL`.
`intentionally removed` with no supporting sentence in the change's own artifacts is **Important**.
Added-only (`J = 0`) is never a finding. **An unadjudicated flag is treated as `dropped`, not
waived.** Nothing here refuses, halts, or edits a change; it flags, and a human adjudicates.

<!-- END INJECTABLE -->

## When it runs

The trigger is the presence of a `## MODIFIED Requirements` heading in the change's delta — not
capability overlap, not batch membership, not requirement count. One block is enough. **Zero blocks
means the check does not apply, and that is reported as such rather than as a pass.**

## What it compares against

The live specification **as it stands in the working tree at the moment of the check**, never as the
delta was authored and never a git revision. A correct block goes stale when anything else reaches
the live spec first: a sibling in the same batch, a change archived from an earlier batch, a small
change landed in between, a hand edit.

## Running step 3

Two enumerations, one per side. Scope each to its own requirement's block rather than the whole
file, or an `## ADDED Requirements` heading in the same delta will be counted as part of the
modified one:

```
# the delta's block
sed -n '/^### Requirement: <Name>$/,/^\(###\|##\) /p' <change>/specs/<capability>/spec.md \
  | grep -c '^#### Scenario:'

# the live requirement's block
sed -n '/^### Requirement: <Name>$/,/^\(###\|##\) /p' openspec/specs/<capability>/spec.md \
  | grep -c '^#### Scenario:'
```

Swap `-c` for `-n` to get the headings themselves, which is what the `-`/`+` lines report.

## Why step 1 comes first

A rename and a deletion are byte-identical to a comparison of headings, and exactly one of them
destroys a live normative statement. A comparison that resolves renames at any later point reports
every renamed requirement as missing. This is measured, not assumed: the one real execution of an
unordered comparison flagged two items across two changes, and **both were benign** — one of them
caused precisely by an unresolved rename mapping.

## Honest limits

**Rename resolution does not eliminate false positives, and must not be described as though it
does.** A rename mapping names requirements, not scenarios. A scenario renamed in place — its
heading rewritten to widen its scope, its behaviour retained — stays flagged, and no ordering
catches it. That was the second of the two measured flags.

**Both directions give a hint, and it is only a hint.** Reporting `+K` alongside `-J` is not blind
here: a deletion leaves `-1 added 0`, while a rename in place leaves `-1 added 1`, because the new
heading arrives as an addition. Measured on a real block — deleting one scenario reported
`live 4 -> delta 2 (+0 added, -2 missing)` and renaming one in place reported
`live 4 -> delta 3 (+1 added, -2 missing)`. **Do not promote that to a distinction.** A change may
legitimately delete one scenario and add an unrelated one, which produces the same pair; and `K` says
nothing about *which* addition corresponds to which absence. Treat a non-zero `K` beside a non-zero
`J` as a reason to read the two headings side by side before adjudicating, never as evidence of a
rename. A residual false-positive rate remains a property of the delta format rather than a defect in
this procedure, which is why the adjudication step exists and why nothing refuses on a flag alone.

**A gutted scenario body is invisible here.** A delta that keeps every heading while emptying a
scenario's WHEN/THEN passes a heading-set comparison. Out of scope, stated so it is not mistaken for
coverage.

## Reporting the denominator

Every run states what it examined: *R modified requirements compared across C capabilities; F
flagged, A adjudicated as renames or intentional removals, D dropped.* A zero that does not carry
what it scanned is indistinguishable from a scan that did not run.

**A non-zero exit from any enumeration command is a failed check, not an empty result.** A command
run from the wrong directory, or against a capability whose live file is absent, yields no headings —
and reading that as "no differences" converts a check that never ran into a confident pass across
every requirement it covered. Same rule the batch-sequencing capability matrix states, for the same
reason.

## What this is not

It is not the live specification set's parse-integrity check, which asks whether the document still
parses after an edit; this asks about content the delta omits, which parses and reads correctly. It
is not an enforcing gate either: the tool that applies a delta may refuse one, but nothing in this
procedure blocks, edits, or auto-corrects a change.
