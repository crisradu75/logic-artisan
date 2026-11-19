# Tasks

## 1. Spec and hook

- [x] 1.1 State the mirror-push exception in the three push requirements and the hook header. Tests marked `requirement: git-guards / A push that deletes or moves a tag on the remote is refused` and `requirement: git-guards / Direct pushes to main are refused` show a mirror push deleting a remote tag and `master` with no line on the hook's stdin, while `--prune` and `--delete` stay refused.
- [x] 1.2 The tag refusal message suggests `git fetch --tags --force`; the move test asserts it.

## 2. Docs

- [x] 2.1 docs and spec map: `README.md`, `DEVELOPER-GUIDE.md` and `.claude/plugins/cla/README.md` wording handed to the docs PR; `openspec/spec-map.md` none affected: its git-guards line names no exception.
