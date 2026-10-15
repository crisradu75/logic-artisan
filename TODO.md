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

Leftover review suggestions (spec-proof empty check (sweep PR)):

- `_bullet_start` in `plugin-tests/tests/consistency/test_mutation_batch_is_opt_in.py` counts any spaced hyphen as a bullet start. It should match only a real list marker.

Leftover review suggestions (spec-writing rules):

- In the one-outcome rule, reword 'supporting SHALL clause' to 'one SHALL per requirement; a second SHALL is a second outcome'. The rule is in `openspec/config.yaml:24` and its mirror in `.claude/plugins/cla/skills/cla-setup/SKILL.md:141`.
- The configurable-values rule's 'as configured' is vague; say the key's exact name as it appears in the config file. The rule is at `openspec/config.yaml:27` and `.claude/plugins/cla/skills/cla-setup/SKILL.md:144`.

Leftover review suggestions (docs task):

- If change B rewords the docs task (`docs and spec map: ...`), add the old wording to `RETIRED` in `cla-setup/scripts/seed_openspec_rules.py`, so repos that seeded it are told to replace it.
- `test_docs_task_sites_agree.py` proves the sites still say the words, not that a review reports a stale doc; that half is the `manual:` line in the archived tasks. A live check of one stale-doc review would close it.
- The lite-pr Docs check has no gate on a repo's rules; it runs wherever the skill runs, with judgement when there is no doc list. Decide whether a repo with no list should skip it.

Leftover review suggestions (orchestration economy rules):

- Rule 12 in `orchestration-economy.md` could name `gh pr view` as the check, since an agent's report can be stale.
- Rule 8 could say its scratch folder should be gitignored, so rule 7's debris check stays quiet. The repo's `.gitignore` has no scratchpad entry today.
