# Tasks

**Every shipped edit (files under `.claude/plugins/cla/`) cites no issue or pull request number of this repo.** State the lesson in words.

## 1. New rules

- [x] 1.1 Propose asks a protected change to list its rejected alternatives in `design.md`. Test: `test_propose_asks_a_protected_change_to_list_its_rejected_alternatives` carries `requirement: change-workflow / A protected change records its rejected alternatives`.
- [x] 1.2 Implement edits the delta spec when the build departs on purpose. Test: `test_implement_edits_the_delta_spec_when_the_build_departs_on_purpose` carries `requirement: change-workflow / A build that departs from the spec updates the spec`.
- [x] 1.3 Handoff refreshes the `Risk:` and `Checks:` lines after the fix rounds. Test: `test_handoff_refreshes_the_risk_and_checks_lines_and_keeps_the_rest` carries `requirement: change-workflow / The pull request body is current after the review rounds`.

## 2. Wording and placement

- [x] 2.1 The check count in both entry points is the number the checklist defines itself, and the guard reads that number from the checklist. Tests: `test_advertised_check_count_matches_the_definitions`, `test_the_high_yield_check_count_leaves_out_the_overlay_labels`.
- [x] 2.2 Checks 0a to 0c are stack-neutral. Test: `test_generic_checks_0a_to_0c_name_no_one_stack`.
- [x] 2.3 The autonomy exceptions list the `git_state` halt and the precheck ask; the full gate rule sits in Handoff's gate rules. Tests: `test_the_halts_the_skill_describes_elsewhere_are_listed_as_exceptions`, `test_handoffs_gate_rules_run_the_one_full_gate_on_the_final_commit`.
- [x] 2.4 Implement's post-checks move to `references/implement-checks.md`; the reference list and `review-change/SKILL.md` are corrected. Tests: `test_the_references_list_files_each_shared_file_under_one_read_condition`, `test_review_change_says_it_only_reports_and_names_what_spec_to_pr_reads`.

## 3. Docs and gate

- [x] 3.1 docs and spec map: none affected: the README files, `CLAUDE.md` and `DEVELOPER-GUIDE.md` go in the PR body for the main session; no skill or spec was added or renamed.
