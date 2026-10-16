# TODO

Leftover review suggestions (docs-task review gaps fix):

- `review-change/references/checklist.md` (Rewrite) reads the live spec at `git merge-base HEAD <default-branch>`, while dispatch.md now anchors its diffs on `<pr-base>`; on a stacked change the two bases differ. Decide which one the Rewrite rule wants.
- `subagent-brief.md` line 121 uses `<branch>` and the quoted block uses `HEAD`. That is right (the orchestrator runs the first, the reviewer the second) but unsaid; same for `revise.md` line 37.
- `model-routing.md` second-pass paragraph: "the docs check" names no section (`revise.md` calls it "Docs currency", lite-pr "Docs check"), and "It reviews the fix diff" now reads as if "It" were "other fixes"; write "Round 2 reviews".
- "a Suggestion-level fix is not one of those other fixes" (`revise.md`, `model-routing.md`) is a stipulation: such a fix is another fix that cannot trigger a round. Say "does not count as one of those other fixes". Likewise "(a docs-currency fix is neither)" in the Flags row and the resume rule should say "counts as neither", since a stale doc is an Important finding.
- `lite-pr/SKILL.md` Docs check: the parenthetical `(`cla.io/project-facts.md`, "Doc-sweep paths", or the docs you picked)` reads as three alternatives; write "the "Doc-sweep paths" section of `cla.io/project-facts.md`, or the docs you picked". Step 4 does not repeat the Suggestion clause, because step 1 fixes only Critical and Important findings; say so or add the clause.

Leftover review suggestions (spec map):

- The fence tracker has three known corners, each of which misleads it only when it lines up with a fence never closed inside a list item and a later stray fence: a run-on line that begins with an inline code span (`` ```x``` ``) ends the item too early; a run-on line that begins with a number and a dot, such as `2026.`, ends the item too early because it reads as an ordered-list marker; an HTML comment at column 0 right after the item's paragraph text keeps the item open too long.

Leftover review suggestions (todo-docs-copilot):

- The scenario "The shipped manifest is read" in "Disclosing the Copilot CLI install is untested" documents the manifest carve-out but the SHALL sentence states no obligation for the manifest; its test (`test_the_shipped_copilot_manifest_does_not_say_the_install_is_untested`) is the only guard. Keep the scenario as documentation or move the check out of the spec.
- `main()` in `.claude/skills/release/scripts/check_copilot_models.py` still lets a `TypeError` from `dict(MODEL_MAP)` or a `SyntaxError` from importing `sync_copilot_agents.py` escape as a traceback, which exits 1 and reads as "ID missing". Catch `Exception` around the map read and return 2.
