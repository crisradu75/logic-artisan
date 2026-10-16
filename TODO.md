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

Leftover review suggestions (spec map):

- `map_links` still counts a link that does not render as one: an escaped `\[x\](..)`, an image `![x](..)`, a line in an indented code block, and a link on a line with an unpaired backtick (`_mask_code_spans` then masks nothing). Skip those forms, or treat such a line as unreadable.
- A reference definition `[b]: specs/beta/spec.md` that no `[text][b]` uses still counts as linking beta. Count a definition only when its label is used.
- A declared glob that also matches a binary or non-UTF-8 file exits 2 with "cannot read the spec map". Match only `.md` files, or report the file as a PROBLEM line.
- Retiring a whole spec may have a mirror trap (not checked): the spec stays live until archive, so a map link removed in the change would be reported as an unlinked spec, and one kept would dangle after archive. Decide how the rule should read a REMOVED capability.
- A setext heading (`Spec map` with a `---` underline) in the facts file is not read as the spec map heading or as a near miss, so the rule stays off without a word. Detect it as `_reads_as_map_heading` does for ATX headings.
- A map link to a file git ignores, or with the wrong case on Windows or macOS, passes the `is_file()` test in `check_spec_map` although the link is broken on GitHub. Check the path against the exact-case file list instead.
- A fence inside a blockquote (`> ```) is not recognised as a fence by `_fence_step`, so a link shown in such an example counts as linking its spec. Strip the quote markers before matching, as the list marker is handled.
- The fence tracker has three known corners, each of which misleads it only when it lines up with a fence never closed inside a list item and a later stray fence: a run-on line that begins with an inline code span (`` ```x``` ``) ends the item too early; a run-on line that begins with a number and a dot, such as `2026.`, ends the item too early because it reads as an ordered-list marker; an HTML comment at column 0 right after the item's paragraph text keeps the item open too long.
