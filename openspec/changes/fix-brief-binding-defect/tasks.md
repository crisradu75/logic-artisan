## 1. Re-derive the anchors before editing

- [ ] 1.1 Re-run the anchor measurements and record the values inline, because a line number measured at proposal time is stale the moment another change lands: `wc -l .claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md .claude/plugins/cla/skills/spec-to-pr/SKILL.md .claude/plugins/cla/skills/spec-to-pr/references/revise.md .claude/plugins/cla/skills/review-change/references/checklist.md` — measured: `<paste the four counts>`
- [ ] 1.2 Locate the four edit sites by content, not by the line numbers in `design.md`: `grep -n '^### 2\. Task\|^### 5\. Done when' .claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md`, `grep -n 'adjudicate every' .claude/plugins/cla/skills/review-change/references/checklist.md`, `grep -n '^### Verified claims' .claude/plugins/cla/skills/review-change/references/checklist.md`, `grep -n 'Round N (N ≥ 2)\|No capitulation on discharge' .claude/plugins/cla/skills/spec-to-pr/references/revise.md` — measured: `<paste the hits>`
- [ ] 1.3 Re-run the blast-radius check and confirm both citing sites still name the brief by slot list: `grep -rn 'subagent-brief' .claude/plugins/cla/` — measured: `<paste the hits>`. If a third citing site now exists, add it to the check in task 4.2 before proceeding.

## 2. The brief's authority contract (`subagent-brief.md`)

- [ ] 2.1 In §2 ("Task — one sentence, one deliverable"), add the fix-brief form: keep the existing one-sentence form as the unmarked default for a build-this dispatch, and add the three named fields for a dispatch whose purpose is to remedy a defect — `**Defect (binding).**`, `**Facts this defect rests on (checkable).**` with the row shape `- <claim> — source: <path:line | command> — [agent-reported | orchestrator-verified]`, and `**Candidate remedy (rejectable).**`. Use the field names verbatim from `design.md` "Pinned implementation parameters".
- [ ] 2.2 In §2, state the three authority levels in one short table or list — binding / rejectable / checkable, with who may overturn each and how — so the contract is legible from the slot itself rather than only from the terminal contract.
- [ ] 2.3 In §2, state the three fact-row outcomes: all rows hold → proceed; a row is wrong and the defect does not survive its correction → return the remedy rejected without implementing; a row is wrong but the defect survives → correct it, proceed, and report the correction.
- [ ] 2.4 In §5 ("Done when"), add the fix-brief terminal-contract block verbatim from `design.md` "Pinned implementation parameters" — the `done` / `blocked` / `remedy-rejected` statuses, the defect-check evidence requirement, the explicit "evidence the remedy was applied is NOT evidence the defect is gone" line, and the never-omitted `Fact corrections:` field. Keep the existing default block as the form for a non-fix dispatch.
- [ ] 2.5 In §5, state that a brief unable to name a defect check is a brief whose defect is not grounded, rather than a dispatch exempt from the contract.
- [ ] 2.6 Confirm no slot was renamed, renumbered or added: `grep -n '^### [0-9]\.' .claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md` returns the same five headings as task 1.2 recorded — measured: `<paste the hits>`.
- [ ] 2.7 Confirm the added prose is portable synced core — no repo token, no dev-tree path, no absolute developer path: `python3 .claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py` — measured: `<paste the exit status and summary line>`.

## 3. Orchestrator-specified remedies (`spec-to-pr`)

- [ ] 3.1 In `SKILL.md`'s Review phase, in the step that applies each Critical and Important finding by direct Edit/Write and then re-validates that the fix landed, add the orchestrator-specified-remedy check: where the orchestrator decided the remedy itself, the re-validation additionally reads the change's own `design.md` rejected-alternatives content and confirms the applied remedy does not reintroduce one.
- [ ] 3.2 In `SKILL.md`'s Review phase, require the marker `remedy: orchestrator-specified` on the finding record for each such remedy, and require the marks to surface in the terminal report when no later round reads that diff.
- [ ] 3.3 In `references/revise.md`, extend the INT-CAP no-capitulation step so that an orchestrator-specified remedy's re-read includes the same `design.md` rejected-alternatives check, and carries the same marker.
- [ ] 3.4 In `references/revise.md`, in the round N ≥ 2 scoping section, require the dispatch to name which hunks in the previous fix commit carry the orchestrator-specified marker and to check each against the same rejected-alternatives content.
- [ ] 3.5 In `SKILL.md`'s Revise stub, add the one-line load-bearing invariant for the above, since the stub must stay self-sufficient when `revise.md` is not reloaded.
- [ ] 3.6 State explicitly, in both `SKILL.md` and `revise.md`, that this control does not raise any round cap and is weaker than an independent reader. Confirm no cap moved: `grep -n 'pr-rounds\|review-rounds' .claude/plugins/cla/skills/spec-to-pr/SKILL.md .claude/plugins/cla/skills/spec-to-pr/references/revise.md` shows the same defaults as before the edit — measured: `<paste the hits>`.

## 4. Fact-row provenance and the bounded widening (`checklist.md`)

- [ ] 4.1 In the cost-offload paragraph, require every row the dispatched fact-gathering agent returns to carry a provenance field on the row — `agent-reported` or `orchestrator-verified` — and state that the orchestrator may not relabel a row as verified without re-running that row's own resolving command or read.
- [ ] 4.2 In the same paragraph, replace the adjudication sentence with the widened, bounded rule verbatim from `design.md`: adjudicate every ✗ row as now, **and** re-measure every row — ✓ or ✗ — that a Critical or Important finding depends on; a row supporting only a Suggestion or no finding stays agent-reported and is reported as such.
- [ ] 4.3 In the same paragraph, state the cost as proportional to the Critical and Important findings produced rather than to the row count, and state that re-measuring every row is rejected because it restores the context cost the offload exists to avoid.
- [ ] 4.4 At `### Verified claims` (the report-format block and its "Why `### Verified claims` is mandatory" note), require the provenance tag on every row and state that the section may carry no untagged row.
- [ ] 4.5 State that the tag travels with the row into the context brief and into any finding derived from it, which inherits the tag until the row is re-measured.
- [ ] 4.6 Add the two run-record counts — `rows_remeasured` and `rows_remeasured_disagreed` — where the review's run record is defined, so the widening's real cost and catch rate can be priced from the ledger rather than re-argued.

## 5. Verify

- [ ] 5.1 Run the area suite for the two skills touched: `pytest plugin-tests/tests/skills` — measured: `<paste the summary line>`.
- [ ] 5.2 Run the conformance and consistency areas, which police synced-core portability and SKILL.md reference integrity: `pytest plugin-tests/tests/conformance plugin-tests/tests/consistency` — measured: `<paste the summary line>`.
- [ ] 5.3 Confirm every reference this change adds resolves: re-run task 1.2's greps against the edited files and confirm each cross-reference (`design.md` rejected alternatives, the brief's §2/§5, the checklist's cost-offload paragraph) is named by content that exists — measured: `<paste the hits>`.
- [ ] 5.4 Dry-read one real fix brief against the new contract: take the most recent fix dispatch in this repo's run notes, rewrite its slot 2 and slot 5 in the new form, and confirm every required field has content that is not `n/a`. If a field can only be filled with `n/a`, the contract is wrong and this task fails rather than the field being waived.
- [ ] 5.5 Before the PR: `pytest plugin-tests` and `node --test plugin-tests/node/mechanical-checks.test.mjs`, each once — measured: `<paste both summary lines>`.
