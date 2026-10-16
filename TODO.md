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

Leftover review suggestions (docs-task review gaps fix):

- `review-change/references/checklist.md` (Rewrite) reads the live spec at `git merge-base HEAD <default-branch>`, while dispatch.md now anchors its diffs on `<pr-base>`; on a stacked change the two bases differ. Decide which one the Rewrite rule wants.
- `subagent-brief.md` line 121 uses `<branch>` and the quoted block uses `HEAD`. That is right (the orchestrator runs the first, the reviewer the second) but unsaid; same for `revise.md` line 37.
- `model-routing.md` second-pass paragraph: "the docs check" names no section (`revise.md` calls it "Docs currency", lite-pr "Docs check"), and "It reviews the fix diff" now reads as if "It" were "other fixes"; write "Round 2 reviews".
- "a Suggestion-level fix is not one of those other fixes" (`revise.md`, `model-routing.md`) is a stipulation: such a fix is another fix that cannot trigger a round. Say "does not count as one of those other fixes". Likewise "(a docs-currency fix is neither)" in the Flags row and the resume rule should say "counts as neither", since a stale doc is an Important finding.
- `lite-pr/SKILL.md` Docs check: the parenthetical `(`cla.io/project-facts.md`, "Doc-sweep paths", or the docs you picked)` reads as three alternatives; write "the "Doc-sweep paths" section of `cla.io/project-facts.md`, or the docs you picked". Step 4 does not repeat the Suggestion clause, because step 1 fixes only Critical and Important findings; say so or add the clause.

Leftover review suggestions (spec map):

- `map_links` still counts a link that does not render as one: an escaped `\[x\](..)`, an image `![x](..)`, a line in an indented code block, and a link on a line with an unpaired backtick (`_mask_code_spans` then masks nothing). Skip those forms, or treat such a line as unreadable.
- A reference definition `[b]: specs/beta/spec.md` that no `[text][b]` uses still counts as linking beta. Count a definition only when its label is used.
- A declared glob that also matches a binary or non-UTF-8 file exits 2 with "cannot read the spec map". Match only `.md` files, or report the file as a PROBLEM line.
- Retiring a whole spec may have a mirror trap (not checked): the spec stays live until archive, so a map link removed in the change would be reported as an unlinked spec, and one kept would dangle after archive. Decide how the rule should read a REMOVED capability.
- A setext heading (`Spec map` with a `---` underline) in the facts file is not read as the spec map heading or as a near miss, so the rule stays off without a word. Detect it as `_reads_as_map_heading` does for ATX headings.
- A map link to a file git ignores, or with the wrong case on Windows or macOS, passes the `is_file()` test in `check_spec_map` although the link is broken on GitHub. Check the path against the exact-case file list instead.
- A fence inside a blockquote (`> ```) is not recognised as a fence by `_fence_step`, so a link shown in such an example counts as linking its spec. Strip the quote markers before matching, as the list marker is handled.
- The fence tracker has three known corners, each of which misleads it only when it lines up with a fence never closed inside a list item and a later stray fence: a run-on line that begins with an inline code span (`` ```x``` ``) ends the item too early; a run-on line that begins with a number and a dot, such as `2026.`, ends the item too early because it reads as an ordered-list marker; an HTML comment at column 0 right after the item's paragraph text keeps the item open too long.
