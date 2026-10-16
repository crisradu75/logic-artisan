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

Leftover review suggestions (spec-writing rules):

- In the one-outcome rule, reword 'supporting SHALL clause' to 'one SHALL per requirement; a second SHALL is a second outcome'. The rule is in `openspec/config.yaml:24` and its mirror in `.claude/plugins/cla/skills/cla-setup/SKILL.md:141`.
- The configurable-values rule's 'as configured' is vague; say the key's exact name as it appears in the config file. The rule is at `openspec/config.yaml:27` and `.claude/plugins/cla/skills/cla-setup/SKILL.md:144`.

Leftover review suggestions (docs task):

- If change B rewords the docs task (`docs and spec map: ...`), add the old wording to `RETIRED` in `cla-setup/scripts/seed_openspec_rules.py`, so repos that seeded it are told to replace it.
- `test_docs_task_sites_agree.py` proves the sites still say the words, not that a review reports a stale doc; that half is the `manual:` line in the archived tasks. A live check of one stale-doc review would close it.
- The lite-pr Docs check has no gate on a repo's rules; it runs wherever the skill runs, with judgement when there is no doc list. Decide whether a repo with no list should skip it.

Leftover review suggestions (orchestration economy and bullet fix sweep):

- Rule 8 in `orchestration-economy.md` says an ignored `scratchpad/` keeps rule 7's debris check quiet. The check lists ignored paths too, so the folder stays quiet only if it exists before the before snapshot. Say to create it first.
- Rule 12 in `orchestration-economy.md` names only `gh pr view`, which shows open or merged state but not whether checks are green. Add `gh pr checks` for the green case.
- `_flat` in `plugin-tests/tests/consistency/test_mutation_batch_is_opt_in.py` also tags a `- ` or `* ` line inside a fenced code block and a `* * *` rule line as bullet markers. CLAUDE.md has neither today.

Leftover review suggestions (Copilot manifest and release-drift check):

- The words "untested in a live Copilot CLI" are hard-coded in the plugin-distribution spec, the docs test and five documents, and the root `plugin.json` description ships inside the release tag, which is never moved. When the install is first run in a real Copilot CLI, every one of these needs editing, and the tagged description stays stale. Consider keeping the claim out of the shipped manifest.
- The "Installing from GitHub Copilot CLI" requirement joins the install line and the duty to disclose that it is untested. Two outcomes; split it if the disclosure outlives the first live test.
- Tasks 2.1, 2.2, 3.1, 3.2 and 4.1 in the change run past the roughly 40-word task rule.
- `test_every_doc_offering_the_copilot_install_says_it_is_untested` checks that two phrases appear somewhere in each doc, not next to the install command.
