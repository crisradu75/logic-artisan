## 1. Rewrite

- [x] 1.1 Rewrite `CLAUDE.md` to rules only, keeping the release line and the "Before opening a PR" row in their exact format. measured: 1422 words, from 4494.
- [x] 1.2 Move the script table and layout trees to DEVELOPER-GUIDE §11, correcting stale rows; move rationale and full rule wording to §12; move distribution and versioning history to "Release and distribution history".
- [x] 1.3 Update the companions: `release/SKILL.md`'s closed 0.x paragraph, DEVELOPER-GUIDE's pointers to CLAUDE.md sections, the plugin README's skills-with-tests count, and mutant-batch comments citing moved text.
- [x] 1.4 Diff the old `CLAUDE.md` against the new one and list every dropped rule (proposal).

## 2. Gate

- [x] 2.1 Drop `CLAUDE.md` from the path-count and diagram floors in `test_docs_name_shipped_paths.py`, floor DEVELOPER-GUIDE's diagram, and re-anchor the `test_doc_facts` and `test_docs_name_shipped_paths` mutants.
- [x] 2.2 Mutation batches over every touched guard, all killed; the full suite parallel and serial on one tree with matching counts; the node suite; `openspec validate --specs --strict`.
