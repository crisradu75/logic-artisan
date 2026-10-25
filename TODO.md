# TODO

Leftover review suggestions (todo sweep):

- `model-routing.md` second-pass paragraph now names the "Docs currency" (`revise.md`) and "Docs check" (lite-pr) headings, so a heading rename makes it wrong with no test noticing. Name the check without the headings, or add a test that the headings exist.
- `lite-pr/SKILL.md` step 4 says "Unlike `revise.md`, this step has no Suggestion clause", which compares against a sibling file. The reason given (step 1 fixes only Critical and Important findings) stands alone; drop the comparison.
- `subagent-brief.md` and `revise.md`: the `<branch>` versus `HEAD` explanation sits in a parenthesis; move it to a sentence of its own.
- `review-change/references/checklist.md` Rewrite rule: "reaches a prompt or a command" is loose (only a command is run here), and the sentence partly repeats the placeholder check in `dispatch.md`.
- `plugin-distribution` spec: the new "SHALL NOT say the install is untested" sentence names the manifest, which the spec-level rules allow only as an interface; decide whether it belongs in the spec or in the test.
- `_later_closer_in` stops at a line of a different quote depth, but a lazy continuation line of a quoted paragraph (a quoted line with a stray backtick and a link, then an unquoted line with the closing backtick) is part of the paragraph on the page. Allow a lower depth when the line does not end the paragraph.

Leftover review suggestions (stash guard, issue 398):

- In `ask-destructive-git.py`, give the stash block its own try/except. An exception from it (for example a ValueError from a NUL in a `-C` path) lands in the shared handler, which logs "the working-tree discard check raised" and skips the discard and clean checks. Append the stash unchecked reason and log "stash check raised" instead.
- A command whose stashes run in several directories gets the "COULD NOT BE RUN" stash reason, although the check was skipped on purpose. Use a separate message that says to check each directory.

Leftover review suggestions (PR for issue 408 prose cleanups):

- In `skills/review-change/references/dispatch.md` (Task Reviewer, "more than 5 subtasks"), the parenthetical naming the Implement-phase delegation count sits inside a prompt the reviewer never needs it for; consider reducing it to "(per task)".
- The "(by hand, not a `mutate.py` batch)" note on the three Mutation gate headings names a dev tool that does not ship; consider "not an automated mutation batch".
- Same-kind repo-specific leftovers still in shipped prose (not in the approved six): `review-change/references/dispatch.md:41` and `project-review/references/review-agents.md:84,113,127` (allocation-math, apps/packages split), `review-change/references/checklist.md:44,76,105` (i18n JSON, allocation-math), `lite-pr/SKILL.md:69` ("Allocation math"), `spec-to-pr/references/precheck.md:15` and `ship.md:59-61` (apps/*, packages/*), `agents/doc-sweeper.md:20` and `agents/fact-gatherer.md:69-70` (example paths), `multi-spec/references/review-gate.md:45`.

- Review of the shape-decision V3 PR: the floor-history comment in plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py (near the scan floor) has no entry for the 111 to 112 floor move made when shape-decision/references/question-form.md was added.

- Review of the reviewer `line` wording PR: the new sentence in the three reviewer agents (and Copilot copies) does not say that context lines count when counting forward through the hunk; consider adding "counting context and added lines".

- Review of the catalog-pin docs PR: README.md line 60-61 states flatly that Copilot treats CLA as a 1.0 plugin; consider 'per GitHub's docs, ...' and splitting the long line at 'A 1.0 plugin offers'.
