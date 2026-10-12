# Tasks

## 1. Verify contracts

- [ ] 1.1 Not run: no `Workflow` tool was available to the implementing session, and the new agents register only at the next session start. No doc settles this; verify by running one `Workflow` `agent()` with `agentType: "cla:code-reviewer"` and `model: "opus"`, and one without `model`, and read each model from its transcript. Done when design Context records both; if `model` does not override, stop before 3.3.

## 2. Agents and their test

- [x] 2.1 Add the conformance test. It fails on any `agents/*.md` missing `name`, `description` or a haiku/sonnet/opus `model`, or whose `tools` list includes Edit, Write, NotebookEdit or Bash. Carry the comment `requirement: review-agents / The plugin ships its own read-only reviewers`.
- [x] 2.2 Add `code-reviewer` (sonnet), `silent-failure-hunter` (opus) and `comment-analyzer` (sonnet) with original prompts, per design Decision 3. Done when the conformance test passes, and `check_no_project_tokens.py` and the hardcoded-path test pass.
- [x] 2.3 Add a mutation batch for the conformance test under `plugin-tests/mutants/conformance/`. Run it once, and read each test that kills a mutant. Done when every mutant is killed.

## 3. Dispatch wiring

- [x] 3.1 Replace "read the hunks with `git diff`" with the diff-file step (Decision 1) in Revise round 1, lite-pr Review and brief slots 3 and 4. Done when a grep finds no reviewer told to run `git diff`.
- [x] 3.2 Revise round N ≥ 2 passes the fix diff as a diff file instead of pasting it into each prompt. Done when `revise.md`'s "Round N" section names a diff file and no inlined diff.
- [x] 3.3 Name the three agent files in `model-routing.md`'s "Routing table" (Decision 4); the sizing table keeps its rows and its one override. Add a consistency test, comment `requirement: review-agents / Review sizing names each reviewer it uses`, passing when every named file exists.
- [x] 3.4 Add a mutation batch for the 3.3 consistency test under `plugin-tests/mutants/consistency/`. Run it once and read each killing test. Done when every mutant is killed.
- [x] 3.5 Point Revise's dispatch list, `model-routing.md`'s dispatch-name paragraph and lite-pr at `cla:<name>` for the three reviewers. Done when a grep for `pr-review-toolkit:code-reviewer`, `:silent-failure-hunter` or `:comment-analyzer` in shipped files returns nothing.
- [x] 3.6 Update each text listing the agents or the `pr-review-toolkit:` dispatch form: plugin README (dependency row, phase table, layout), root README and DEVELOPER-GUIDE layouts, `model-routing.md`'s "two haiku agents", `run-log-schema.md`, the `log_run.py` key comment. Done when none is stale.
- [ ] 3.7 Add the line `manual: A reviewer reads the change from a diff file: needs a live review round`. Done when one lite-pr review round shows each brief naming a diff file, and `git status` is clean afterwards.

manual: A reviewer reads the change from a diff file: needs a live review round

## 4. Gate

- [ ] 4.1 Run `pytest plugin-tests -q -n auto --dist loadfile` and `openspec validate --specs --strict` once each. Done when both pass and the pass and skip counts match a serial run.

## Workflow follow-up

- Release as a minor version after merge, through `/release`.
