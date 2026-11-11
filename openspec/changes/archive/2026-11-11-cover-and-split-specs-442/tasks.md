# Tasks

## 1. Specs

- [x] 1.1 Add the delta specs: new `instruction-files`, `cla-setup`, `copilot-cli`, `git-guards`, `guard-warnings`; `guard-hooks` split; moved requirements removed from `repo-context` and `plugin-distribution`. `openspec validate --specs --strict` passes after archive.

## 2. Tests

- [x] 2.1 Point existing `requirement:` lines at the new homes. `check_spec_proof.py --root .` reports no unproven requirement.
- [x] 2.2 Test `instruction-files / Every instruction file is read`: the existing both-named test carries the marker.
- [x] 2.3 Test `instruction-files / A rule is written to the file the repo already uses` and `An instruction file is never created silently`: the reference states the file chosen in each repo setup and never creates one silently.
- [x] 2.4 Test `cla-setup / Setup asks the test-proof question once`: the skill asks once, only without an existing line, and writes only after a yes.
- [x] 2.5 Test `git-guards / A push to the remote's own default branch is refused`: the existing `pre-push` tests carry the marker.
- [x] 2.6 Test the split `git-guards` ask requirements and the three `guard-hooks` block requirements: each existing hook test carries the marker of the outcome it checks.

## 3. Docs

- [x] 3.1 docs and spec map: `openspec/spec-map.md` (new specs linked from workflow steps; one line saying `CLAUDE.md` governs the skills with no spec); none affected: no other doc names these specs.
