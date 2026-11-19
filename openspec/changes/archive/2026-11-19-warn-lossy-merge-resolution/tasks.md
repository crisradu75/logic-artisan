# Tasks

## 1. Hook

- [x] 1.1 `warn-lossy-merge-resolution` warns before a merge-concluding `git commit` or `git merge --continue` whose result lacks lines `MERGE_HEAD` added since the merge base, naming files and up to five lines each. Tests marked `requirement: guard-warnings / A merge commit that drops lines the other side added warns` cover take-ours, both sides kept, a deliberate replacement, `merge --continue` and the dispatcher's context output.
- [x] 1.2 Silent with no merge in progress, a broken repository, no git, a git that prints garbage or raises, and bad input; the tests assert each.
- [x] 1.3 Advisory in the Bash dispatcher and listed in `_READS_COMMAND_ONLY`; it reads wrapper bodies itself, so a command with three commits makes five git calls, as a test asserts.

## 2. Docs

- [x] 2.1 docs and spec map: `README.md`, `DEVELOPER-GUIDE.md` and `.claude/plugins/cla/README.md` (hook tables, counts, the guard-limits note), `CHANGELOG.md`; `openspec/spec-map.md` none affected: its guard-warnings line names no hook.
