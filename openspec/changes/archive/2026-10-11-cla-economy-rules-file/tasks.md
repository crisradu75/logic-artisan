## 1. Spec

- [x] 1.1 Apply the `repo-context` delta; confirm the spec still holds 8 requirements and `plugin-distribution` is unchanged.
- [x] 1.2 `openspec validate cla-economy-rules-file --strict` and `openspec validate --specs --strict` exit 0. The archive step applies the delta; nothing is hand-merged.

## 2. Portable sources and the reference

- [x] 2.1 Write `skills/_shared/references/economy-rules-file.md`. It authors only the framing, model by task (cheap model for sweeps and mechanical work, Sonnet for authoring and fixes, Opus only where judgement carries risk, an explicit `model:` on every dispatch) and the quality floor (claims cite file:line, protected rules kept, real-file check on copies, debris check, owner-approved before/after for score- or gate-moving changes, cleanup after one yes/no), plus two include markers. The cost rules (complete first briefs, test cadence, one PR at a time per area, handoff file, Opus implementers, debris) come from the inlined `orchestration-economy.md`; the risk call, table and round 2 rule come from the inlined sizing section. It holds no copy of either.
- [x] 2.2 Reword `orchestration-economy.md` so it reads without a plugin: the intro names no chain skill, rule 1 has no `${CLAUDE_PLUGIN_ROOT}` path, rule 6 points at the risk signals instead of "`model-routing.md`". Keep the strings `git status --porcelain --ignored --untracked-files=all` and `explicit `model:``.
- [x] 2.3 Reword the "Review sizing by risk" section of `model-routing.md` the same way: no "Every skill ... cites this section" opening, no `lite-pr`, `Handoff Issue` or `--pr-rounds`, "under `skills/`" and "as `revise.md` describes" restated as "files that steer an agent (skill, prompt and agent-definition files, such as `.md` files under `skills/`)", the skill reviewer named "where installed". Keep every pinned string: "Unsure means high", "only after round 1 fixed a Critical", "at round 1's final level, never lower", "Prose-dominant", "outside `skills/` is not prose-dominant", the missing-line sentence, and the 3 table rows. If the prose-dominant rule cannot read true for any repo, drop it from the inlined range and justify the footnote in the table's comment.
- [x] 2.4 Add a begin and an end marker comment in `model-routing.md` around the heading through the Round 2 paragraph, excluding the "Artifact-class override" subsection. Update the review-sizing mutation batch anchor `diff as high risk. The run records that as a Handoff Issue` to the new wording.
- [x] 2.5 Add the reference's row to `skills/_shared/README.md`.
- [x] 2.6 Test in `plugin-tests/tests/consistency/test_review_sizing_single_source.py`: add the new reference to the "These carry no row either" dict, and the pointer check to the `_CHAINS` loop; the shipped reference and both edited sources pass `python3 .claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py` (exit 0).
  <!-- requirement: repo-context / Setting up a repo's cla.io tree and economy rules file -->

## 3. The write step and the contract

- [x] 3.1 Add a Part 1 item to `skills/cla-setup/SKILL.md`: one regex-extractable bash block, guarded `: "${ROOT:?...}"` and on `${CLAUDE_PLUGIN_ROOT}` being non-empty. It runs `mkdir -p "$ROOT/.claude/rules"`, renders the reference with both sources inlined between the markers (everything through `tr -d '\r'`), compares to the existing file through `tr -d '\r'`, writes, and prints `created`, `replaced` or `unchanged`.
- [x] 3.2 Fix every `cla-setup/SKILL.md` sentence the change makes false (re-read each; confirm line numbers first): line 3 (frontmatter "without overwriting anything", "Changes existing files only on the user's yes"), 17 ("Creates only what is missing"), 23-24 ("changes nothing without a yes"), 41-43 (skip anything that exists), 49-51 (create only what is missing, byte-for-byte), 52-53 ("The one unasked edit is item 7's"), 57 (report vocabulary gains `replaced` and `unchanged`), 61 ("Every item is create-if-absent"), 103 ("The one path outside `cla.io/` and `.gitignore` this skill writes").
- [x] 3.3 Fix `DEVELOPER-GUIDE.md` (the `/cla:cla-setup` step: "never overwriting", "apart from that `.gitignore` line it changes an existing file only on your yes") and `.claude/plugins/cla/README.md` (the bootstrap row and the onboarding line); grep both for other mentions.
- [x] 3.4 Leave `openspec/config.yaml` and the item 5 `rules:` block alone.

## 4. Tests (all in `plugin-tests/tests/consistency/`, extracting the block as `test_cla_setup_retired_ledgers.py` and `test_run_notes_stay_local.py` do)

The harness substitutes the plugin root as a literal and runs the block with only `ROOT` set.

- [x] 4.1 No file: the block creates it and reports `created`; the written file has no `paths:` frontmatter.
  <!-- requirement: repo-context / Setting up a repo's cla.io tree and economy rules file -->
- [x] 4.2 An edited copy is replaced and reported `replaced`; a second run reports `unchanged` and the file is byte-identical.
  <!-- requirement: repo-context / Setting up a repo's cla.io tree and economy rules file -->
- [x] 4.3 A full cla-setup run changes no existing file other than the `.gitignore` append and the rules file (hash the tree before and after, `CLAUDE.md` included).
  <!-- requirement: repo-context / Setting up a repo's cla.io tree and economy rules file -->
- [x] 4.4 The written file contains the sizing table and the economy rules from their sources, no `${CLAUDE_PLUGIN_ROOT}`, and none of these plugin-only names: `/cla:`, `lite-pr`, `multi-lite`, `multi-pr`, `multi-spec`, `spec-to-pr`, `Handoff Issue`, `revise.md`, `model-routing.md`, `orchestration-economy.md`, `--pr-rounds`.
  <!-- requirement: repo-context / Setting up a repo's cla.io tree and economy rules file -->
- [x] 4.5 A CRLF copy of the sources and an LF copy render the same output and the second compares `unchanged`.
  <!-- requirement: repo-context / Setting up a repo's cla.io tree and economy rules file -->
- [x] 4.6 The begin and end markers each occur exactly once in `model-routing.md`, and a footnote added after the table still extracts.
  <!-- requirement: repo-context / Setting up a repo's cla.io tree and economy rules file -->
- [x] 4.7 One real test per citing site: `multi-lite`, `multi-pr` and `multi-spec` `SKILL.md` each name `economy-rules-file.md` and copy none of its rules (parametrized, so each site fails alone).
  <!-- requirement: repo-context / Setting up a repo's cla.io tree and economy rules file -->

## 5. Citation sites

- [x] 5.1 `skills/multi-lite/SKILL.md`: name the new reference beside the `orchestration-economy.md` citation in "Run thin".
- [x] 5.2 `skills/multi-pr/SKILL.md`: the same.
- [x] 5.3 `skills/multi-spec/SKILL.md`: the same.
- [x] 5.4 `lite-pr` and `spec-to-pr` keep their sizing-section citations and are not edited.

## 6. Proofs and the final gate

- [x] 6.1 Real-file check: run the new block read-only on copies of this repo's own layout and on a throwaway repo, never a live folder; record `created` on one and `replaced` after a hand edit. Owner-named repos are not available to an agent.
  <!-- manual: Setting up a repo's cla.io tree and economy rules file: owner runs /cla:cla-setup in one real consumer repo after merge -->
- [x] 6.2 Final gate, once on the final commit: `pytest plugin-tests -q -n auto --dist loadfile` (pass and skip counts equal a serial run), `openspec validate --specs --strict`, the debris check (`git status --porcelain --ignored --untracked-files=all` before and after shows no new line outside pytest's temp directory), and one mutation batch over the changed lines of `test_review_sizing_single_source.py`. No version bump, no tag; release is out of scope. measured: parallel run on the archived tree 1987 passed, 1 failed, 8 skipped; the one failure was nine stale requirement markers in `test_run_notes_stay_local.py`, fixed and the two affected files rerun, 29 passed. Not done: no serial run to compare pass and skip counts. `openspec validate --specs --strict` passed before archive, `validate --specs` after. Mutation batch killed 32 of 32. Debris check showed no new non-cache line.
