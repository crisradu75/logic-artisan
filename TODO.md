# TODO

Leftover review suggestions (todo sweep):

- `model-routing.md` second-pass paragraph now names the "Docs currency" (`revise.md`) and "Docs check" (lite-pr) headings, so a heading rename makes it wrong with no test noticing. Name the check without the headings, or add a test that the headings exist.
- `lite-pr/SKILL.md` step 4 says "Unlike `revise.md`, this step has no Suggestion clause", which compares against a sibling file. The reason given (step 1 fixes only Critical and Important findings) stands alone; drop the comparison.
- `subagent-brief.md` and `revise.md`: the `<branch>` versus `HEAD` explanation sits in a parenthesis; move it to a sentence of its own.
- `review-change/references/checklist.md` Rewrite rule: "reaches a prompt or a command" is loose (only a command is run here), and the sentence partly repeats the placeholder check in `dispatch.md`.
- `plugin-distribution` spec: the new "SHALL NOT say the install is untested" sentence names the manifest, which the spec-level rules allow only as an interface; decide whether it belongs in the spec or in the test.
- `_later_closer_in` stops at a line of a different quote depth, but a lazy continuation line of a quoted paragraph (a quoted line with a stray backtick and a link, then an unquoted line with the closing backtick) is part of the paragraph on the page. Allow a lower depth when the line does not end the paragraph.
