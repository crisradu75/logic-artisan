# Tasks

## 1. Hook

- [x] 1.1 `pre-push` refuses a tag delete (all-zero local sha) and a tag move (remote sha set and different), allows a new tag, and lifts only that refusal under `ALLOW_TAG_REWRITE=1`. Tests marked `requirement: git-guards / A push that deletes or moves a tag on the remote is refused` push to a real bare remote.
- [x] 1.2 `ALLOW_PUSH_TO_MAIN=1` lifts only the default-branch refusal; a test shows it no longer lets a tag delete through.
- [x] 1.3 Break the delete check by hand once and confirm a test fails; extend the hook's mutation batch over the changed lines and run it once after the last change.

## 2. Release skill

- [x] 2.1 `/release` tags the release PR's head, proves the tag is on the remote, then merges with `--merge` pinned to the tagged commit, and restarts as a new version if the PR needs another commit. Tests marked `requirement: plugin-distribution / A release is tagged before its catalogs name it` pin the order and the merge flags.

## 3. Docs

- [x] 3.1 docs and spec map: `CHANGELOG.md`, `README.md`, `DEVELOPER-GUIDE.md` and `.claude/plugins/cla/README.md` lines handed to the orchestrator, whose parallel PRs edit those files; `openspec/spec-map.md` updated: the git-guards line names the tag refusal.
