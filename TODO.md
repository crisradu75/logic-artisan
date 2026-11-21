# TODO

Leftover review suggestions. The inbox is emptied by regular sweep PRs.

- No spec scenario covers an overlay that changes a report field another skill reads.
- The untrusted-text rule covers issue and PR text only, not web pages or other tool results; owner to decide whether to widen it.
- Ship's `Checks:` list in `lite-pr/SKILL.md` does not name the no-seam note; the rewrite scenario does not check the `Checks:` line.
- `test_lite_pr_triggers_name_their_references.py` lists only some of lite-pr's references; consider a glob over `references/` instead of a hand list.
- Make the shared "before the move" wording plain in all skills and its test (`test_overlays_are_reachable.py`); consider moving new-worktree's resolver block if `test_skill_lint.py` is relaxed.
- `save-permissions` step 5 verification is optional and cannot catch an accepted-but-dead entry.
