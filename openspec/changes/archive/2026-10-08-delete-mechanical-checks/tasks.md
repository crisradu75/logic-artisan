## 1. Delete

- [x] 1.1 Delete `mechanical-checks.mjs` and `plugin-tests/node/`, and rename project-review's Step 0 reference to `baseline-checks.md` with Part B removed.
- [x] 1.2 Remove the Node suite from CLAUDE.md, DEVELOPER-GUIDE, both READMEs, `cla.io/project-facts.md` and `/release`.
- [x] 1.3 Narrow `check_shipped_tree.py`'s scripts pattern to `.py`, drop `node` from `norecursedirs`, and drop `.mjs` from the scanners.

## 2. Gate

- [x] 2.1 Re-pin the floors and recorded counts in `test_no_hardcoded_plugin_paths.py` and `test_skill_lint.py`, and re-anchor the release and hardcoded-path mutation batches. measured: scan 100 files, 176 placeholder references.
- [x] 2.2 Mutation batches over every touched guard, all killed; the full suite parallel and serial on one tree with matching counts; `openspec validate --specs --strict`.
