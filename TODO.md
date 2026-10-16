# TODO

Leftover review suggestions (spec-proof-checker):

- `manual: <heading>: <reason>` names a heading, not a spec, so one line covers a same-named changed requirement in every spec of a touched change. Fixing it needs a format change to the tasks rule; the limit is documented in the script docstring.

Leftover review suggestions (spec checker fixes, change spec-checker-purpose-note-fixes):

- A Purpose shaped Serves line, sentence on the next line, blank line, more text gets "the Serves line holds more than one sentence" from `purpose_notes`, because the whole first paragraph is read as a wrapped Serves line. The real fault is the extra text after the sentence. Treat the paragraph as wrapped only when its first line does not already end a sentence.
- In `_mask_code_spans`, one unpaired backtick drops every backtick and unmasks the spans that did pair, so a period inside a real span can count as a sentence break. Mask the pairs and drop only the leftover backtick, or document the over-count.
- The `count_sentences` case "Run ``a ` b. c`` now." gives 1 under the old code-span pattern too, so it does not prove that only equal-length backtick runs pair. Replace it with a case the old pattern gets wrong.
- The final `print` in `main` can still raise `OSError` (a closed pipe) outside the `try`, and `_console_safe` falls back to the raw text on an unknown encoding name. Both end as a traceback with exit 1. Return 2 and fall back to ASCII with `backslashreplace`.
- `_git` drops stderr, so a `_base_text` failure names only exit codes. Return stderr from `_git` and put it in the message.
- `test_a_long_archive_path_in_a_deep_repo_reports_no_false_uncovered` passes on Linux and macOS with or without the fix, and skips when the temp path is too long. The fake-git test beside it is the one that runs everywhere.

Leftover review suggestions (docs task):

- If change B rewords the docs task (`docs and spec map: ...`), add the old wording to `RETIRED` in `cla-setup/scripts/seed_openspec_rules.py`, so repos that seeded it are told to replace it.
- `test_docs_task_sites_agree.py` proves the sites still say the words, not that a review reports a stale doc; that half is the `manual:` line in the archived tasks. A live check of one stale-doc review would close it.

Leftover review suggestions (docs-task review gaps):

- Two more statements of round 2's trigger carry no docs-currency carve-out and are not in `_round_2_sites`: the `--pr-rounds` row in the Flags table of `spec-to-pr/SKILL.md`, and the resume rule in `revise.md` that opens "if you cannot tell whether the previous round fixed a Critical" (that one fails safe). Add the phrase or add them to the test.
- `model-routing.md` defines a docs-currency fix as "an edit that brings a stale doc up to date", broader than `revise.md` and lite-pr, where it is the fix of a stale-doc finding the docs check reported. Use one definition.
- `test_docs_task_sites_agree.py` pins the term at each second-pass site, not the "other fixes alone" clause, so the mixed case is unguarded. The sites also do not say whether Suggestion-level fixes count as "other fixes".
- lite-pr's Docs check ends "does not by itself earn step 4's second pass"; "does not count toward step 4's second pass" matches the mixed-case wording better, and `revise.md`'s "as if the doc edits were not there" is clearer than lite-pr step 4's parenthetical.
- `git merge-base` is not in `required-permissions-narrow.json`, so the Implement and Test path checks in `spec-to-pr/SKILL.md` may prompt in an unattended run.
- The review-change prompts in `review-change/references/dispatch.md` say `git diff origin/<default-branch>...HEAD`, which on a stacked branch includes the parent's changes, and carry a "fill it in before sending" aside inside the quoted agent prompt. `subagent-brief.md` says `<branch>` where dispatch.md says `HEAD`.
- lite-pr's Docs check paragraph no longer names `cla.io/project-facts.md` "Doc-sweep paths" beside "the doc list"; only the plan line does.

Leftover review suggestions (orchestration economy and bullet fix sweep):

- Rule 8 in `orchestration-economy.md` says an ignored `scratchpad/` keeps rule 7's debris check quiet. The check lists ignored paths too, so the folder stays quiet only if it exists before the before snapshot. Say to create it first.
- Rule 12 in `orchestration-economy.md` names only `gh pr view`, which shows open or merged state but not whether checks are green. Add `gh pr checks` for the green case.
- `_flat` in `plugin-tests/tests/consistency/test_mutation_batch_is_opt_in.py` also tags a `- ` or `* ` line inside a fenced code block and a `* * *` rule line as bullet markers. CLAUDE.md has neither today.

Leftover review suggestions (Copilot manifest and release-drift check):

- The words "untested in a live Copilot CLI" are hard-coded in the plugin-distribution spec, the docs test and five documents, and the root `plugin.json` description ships inside the release tag, which is never moved. When the install is first run in a real Copilot CLI, every one of these needs editing, and the tagged description stays stale. Consider keeping the claim out of the shipped manifest.
- The "Installing from GitHub Copilot CLI" requirement joins the install line and the duty to disclose that it is untested. Two outcomes; split it if the disclosure outlives the first live test.
- Tasks 2.1, 2.2, 3.1, 3.2 and 4.1 in the change run past the roughly 40-word task rule.
- `test_every_doc_offering_the_copilot_install_says_it_is_untested` checks that two phrases appear somewhere in each doc, not next to the install command.

Leftover review suggestions (session-traps PR, CLAUDE.md):

- The `check_spec_proof.py` trap could also name `--root <worktree>`, which checks that worktree from any cwd (`.claude/plugins/cla/skills/_shared/scripts/check_spec_proof.py:848`).
- The "closes no issue without it" trap is slightly too strong: a closing keyword in the squash commit message, or a sidebar link, also closes the issue. Say "without a closing keyword such as `Closes #N` in the PR body".

Leftover review suggestions (Copilot agents):

- `sync_copilot_agents.py --write` never looks at `com.github.copilot/agents/` for copies whose Claude agent was renamed or removed; it prints "in step" and exits 0 while the consistency test fails. Have the script report or delete such files.
- The model IDs in `MODEL_MAP` are checked against nothing but the script itself; GitHub renames models, and Copilot then silently uses the session model. Decide whether to re-read the supported-models table at each release.
