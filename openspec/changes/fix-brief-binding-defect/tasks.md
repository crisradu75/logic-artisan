## 1. Re-derive the anchors before editing

- [ ] 1.1 Re-run the anchor measurements and record the values inline, because a line number measured at proposal time is stale the moment another change lands: `wc -l .claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md .claude/plugins/cla/skills/spec-to-pr/SKILL.md .claude/plugins/cla/skills/spec-to-pr/references/revise.md` — measured: `<paste the three counts>`
- [ ] 1.2 Locate every edit site by content, not by the line numbers in `design.md`: `grep -n '^### 2\. Task\|^### 5\. Done when' .claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md`, `grep -n 'Round N (N ≥ 2)\|No capitulation on discharge\|Fix-delegate default' .claude/plugins/cla/skills/spec-to-pr/references/revise.md` — measured: `<paste the hits>`
- [ ] 1.3 Re-run the terminal-contract site census and confirm it still returns five hits in the five files the proposal's Impact table names: ``grep -rn 'explicit `done`\|`done`/`blocked`' .claude/plugins/cla/skills/`` — measured: `<paste the hits>`. If a sixth site now exists, classify it as fix-dispatch or not and add it to task 3.4 before proceeding.
- [ ] 1.4 Re-run the blast-radius check and confirm both citing sites still name the brief by slot list: `grep -rn 'subagent-brief' .claude/plugins/cla/` — measured: `<paste the hits>`. If a third citing site now exists, add it to task 2.6 before proceeding.

## 2. The brief's authority contract (`subagent-brief.md`)

- [ ] 2.1 In §2 ("Task — one sentence, one deliverable"), add the fix-brief form: keep the existing one-sentence form as the unmarked default for a build-this dispatch, and add the three named fields for a dispatch whose purpose is to remedy a defect — `**Defect (binding).**`, `**Facts this defect rests on (checkable).**` with the row shape `- <claim> — source: <path:line | command> — [agent-reported | orchestrator-verified]`, and `**Candidate remedy (rejectable).**`. Use the field names verbatim from `design.md` "Pinned implementation parameters".
- [ ] 2.2 In §2, state the three authority levels in one short table or list — binding / rejectable / checkable, with who may overturn each and how — so the contract is legible from the slot itself rather than only from the terminal contract.
- [ ] 2.3 In §2, state the three fact-row outcomes: all rows hold → proceed; a row is wrong and the defect does not survive its correction → return the remedy rejected without implementing; a row is wrong but the defect survives → correct it, proceed, and report the correction.
- [ ] 2.4 In §5 ("Done when"), add the fix-brief terminal-contract block verbatim from `design.md` "Pinned implementation parameters" — the `done` / `blocked` / `remedy-rejected` statuses, the defect-check evidence requirement, the explicit "evidence the remedy was applied is NOT evidence the defect is gone" line, and the never-omitted `Fact corrections:` field. Keep the existing default block as the form for a non-fix dispatch.
- [ ] 2.5 In §5, state that a brief unable to name a defect check is a brief whose defect is not grounded, rather than a dispatch exempt from the contract.
- [ ] 2.6 Confirm no slot was renamed, renumbered or added: `grep -n '^### [0-9]\.' .claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md` returns the same five headings as task 1.2 recorded — measured: `<paste the hits>`.
- [ ] 2.7 Confirm the added prose is portable synced core — no repo token, no dev-tree path, no absolute developer path: `python3 .claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py` — measured: `<paste the exit status and summary line>`.

## 3. The sites that restate the terminal contract (`spec-to-pr`)

A rule added only to the brief leaves every dispatch site briefing against the old two-status
contract. Task 1.3's census is the authority for which sites these are.

- [ ] 3.1 In `SKILL.md`'s Implement phase, at the evidence-based terminal-contract bullet, add that a dispatch whose purpose is to remedy a defect uses the fix-brief form and its three-status contract, and point at `references/subagent-brief.md` §5 rather than restating the block. Do not touch the build-this wording that precedes it.
- [ ] 3.2 In `references/revise.md`, at the fix-delegate default, make the same change: a fix-set delegated here IS a fix dispatch, so its brief takes the fix-brief form and `remedy-rejected` is one of its three valid returns.
- [ ] 3.3 In `SKILL.md`'s Revise stub, update the fix-delegate invariant line to name the three-status contract, since the stub must stay self-sufficient when `revise.md` is not reloaded.
- [ ] 3.4 Confirm no fix-dispatch site still states the two-status contract alone, and that the one non-fix site is untouched: re-run task 1.3's grep — measured: `<paste the hits>`. `multi-spec/references/authoring-brief.md` must be unchanged.

## 4. `remedy-rejected` gets a receiving branch (`revise.md`, `SKILL.md`)

- [ ] 4.1 In `references/revise.md`'s triage step, add the third outcome beside Applied and Deferred-Known-Issue: a delegate return of `remedy-rejected` is a **successful** return that discharges the round's attempt at that finding without discharging the finding — the orchestrator re-decides the remedy and the finding stays open.
- [ ] 4.2 In the same file's exit gate, state that a finding whose delegate returned `remedy-rejected` counts as triaged for the round it was rejected in but is NOT closed, so the gate neither counts it as untriaged residue nor lets it exit silently.
- [ ] 4.3 State explicitly, in both `SKILL.md` and `revise.md`, that a rejection does not consume an extra round and raises no cap. Confirm no cap moved: `grep -n 'pr-rounds\|review-rounds' .claude/plugins/cla/skills/spec-to-pr/SKILL.md .claude/plugins/cla/skills/spec-to-pr/references/revise.md` shows the same defaults as before the edit — measured: `<paste the hits>`.
- [ ] 4.4 In `SKILL.md`'s Revise stub, add the one-line invariant for the third outcome.

## 5. Orchestrator-specified remedies (`spec-to-pr`)

- [ ] 5.1 In `SKILL.md`'s Review phase, in the step that applies each Critical and Important finding by direct Edit/Write and then re-validates that the fix landed, add the orchestrator-specified-remedy check: where the orchestrator decided the remedy itself, the re-validation additionally reads the change's own `design.md` rejected-alternatives content and confirms the applied remedy does not reintroduce one.
- [ ] 5.2 State, in the same step, that where the remedy IS an edit to the change's own `design.md`, the check reads the pre-edit version of that content (`git show HEAD:<path>`), because a document edited by the remedy cannot adjudicate the remedy. This closes the circularity the review found.
- [ ] 5.3 State that a skill applying orchestrator fixes with no OpenSpec change directory — `lite-pr` has none by construction — has no rejected-alternatives document to read, and the check is therefore scoped to skills that operate on a change. Do not name a skill that does not exist in a consuming repo; state the condition, not the roster.
- [ ] 5.4 In `SKILL.md`'s Review phase, require the marker `remedy: orchestrator-specified` on the finding record for each such remedy, and require the marks to surface in the terminal report when no later round reads that diff.
- [ ] 5.5 In `references/revise.md`, extend the INT-CAP no-capitulation step so that an orchestrator-specified remedy's re-read includes the same `design.md` rejected-alternatives check, with the same pre-edit rule, and carries the same marker.
- [ ] 5.6 In `references/revise.md`, in the round N ≥ 2 scoping section, require the dispatch to name which hunks in the previous fix commit carry the orchestrator-specified marker and to check each against the same rejected-alternatives content.
- [ ] 5.7 State explicitly, in both `SKILL.md` and `revise.md`, that this control is weaker than an independent reader and raises no round cap.

## 6. Verify

- [ ] 6.1 Run the area suite for the one skill touched: `pytest plugin-tests/tests/skills/spec-to-pr` — measured: `<paste the summary line>`.
- [ ] 6.2 Run the conformance and consistency areas, which police synced-core portability and SKILL.md reference integrity: `pytest plugin-tests/tests/conformance plugin-tests/tests/consistency` — measured: `<paste the summary line>`.
- [ ] 6.3 Confirm every reference this change adds resolves: re-run task 1.2's greps against the edited files and confirm each cross-reference (`design.md` rejected alternatives, the brief's §2/§5) is named by content that exists — measured: `<paste the hits>`.
- [ ] 6.4 Author a fix brief in the new form against a real historical defect, and confirm every required field has content that is not `n/a`. Source the defect from a real `fix:` commit rather than a stored brief — no brief text is archived anywhere in this repo, so one must be constructed: pick a commit from `git log --grep '^fix: review round' --oneline`, read its diff and the PR body it belongs to for the defect it fixed, and fill slot 2's three fields and slot 5's five return fields from that. **If a field can only be filled with `n/a`, the contract is wrong and this task fails rather than the field being waived.** — measured: `<paste the drafted slot 2 and slot 5>`.
- [ ] 6.5 Confirm the dry-read's defect check is a real command: the brief drafted in 6.4 must name a check that exhibits the defect and is runnable as written. If the historical defect has no such check, say so — that is a finding about the contract's reach, not a task failure — and record which commit it was — measured: `<paste the check, or the finding>`.
- [ ] 6.6 Before the PR: `pytest plugin-tests` and `node --test plugin-tests/node/mechanical-checks.test.mjs`, each once — measured: `<paste both summary lines>`.
