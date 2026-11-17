# Tasks

## 1. Repackage as a source repo

- [ ] 1.1 Move `plugins/mnemo/skills/README.md` to `mnemo-plugin/skills/README.md`, delete `.claude-plugin/` and `plugins/`, and add `VERSION` holding `0.2.0`; `git ls-files` shows no `plugin.json` or `marketplace.json`.
- [ ] 1.2 Add `tests/` with an empty `__init__.py` and an empty `evals/` holding a `.gitkeep`; `python -m unittest discover -s tests` exits 0.

## 2. Release and layout tests

- [ ] 2.1 Shipped-layout test with `scenario: mnemo-release / Per-domain file in the shipped folder`, `/ Plugin manifest returns` and `/ Folder outside the destination shape` comments, each planting the bad file in a temporary copy of the repo.
- [ ] 2.2 Path-map test with a `scenario: mnemo-release / Missing target` comment; it passes on the real tree and fails on a temporary copy naming a missing script.
- [ ] 2.3 Version-equals-tag test with `scenario: mnemo-release / Tagged commit with a matching version`, `/ Mismatch` and `/ Malformed version` comments, run on scratch git repos it creates and tags.
- [ ] 2.4 Version-bump test with `scenario: mnemo-release / Shipped change without a bump` and `/ Docs-only change` comments, on scratch repos with a `main` branch; it fails, never skips, when `main` is missing.
- [ ] 2.5 Harness tests with `scenario: mnemo-release / One command`, `/ Nothing left behind` and `/ Workflow added` comments; the debris test compares `git status --porcelain --ignored` before and after a suite run.

## 3. Schema reader and base schema

- [ ] 3.1 Add the base schema to `mnemo-plugin/mnemo/conventions/` with the nine base fields; a test with a `scenario: note-checks / Required set is pinned` comment fails when the required set changes.
- [ ] 3.2 Implement the schema reader in the check script; tests with `scenario: note-checks / Value containing a colon`, `/ Quoted value`, `/ Inline list with a quoted comma`, `/ Two-level block` and `/ Unsupported construct` comments, plus single-quote `''` and empty-value cases.

## 4. Check subcommands

- [ ] 4.1 Implement `mnemo-plugin/mnemo/scripts/mnemo_check.py` and its subcommand dispatch; tests with `scenario: note-checks / Passing check`, `/ Failing check names the place` and `/ Unknown subcommand` comments, calling the script through `sys.executable` on scratch repos.
- [ ] 4.2 Changed-set tests with `scenario: note-checks / Unchanged note is not examined` and `/ New untracked note is examined` comments.
- [ ] 4.3 Fail-closed tests with `scenario: note-checks / Outside a git repo`, `/ Unreadable file` and `/ Failing run leaves the repo as it was` comments; the last compares file bytes, `git diff --cached` and `HEAD` before and after.
- [ ] 4.4 `links` and `deletions` tests with `scenario: note-checks / Broken relative link`, `/ Web link`, `/ Deleted note still linked` and `/ Deleted note no longer linked` comments.
- [ ] 4.5 `schema` tests with `scenario: note-checks / Missing required field`, `/ Inbox note skips type rules` and `/ Unmarked type field is optional` comments.
- [ ] 4.6 `secrets` tests with `scenario: note-checks / IBAN in an inbox note`, `/ Partly masked card number` and `/ Clean change` comments, plus one case per pattern family in design.md, all with invented values.
- [ ] 4.7 Import test with a `scenario: note-checks / Third-party import` comment, checking every `.py` under `mnemo-plugin/` against `sys.stdlib_module_names`.
- [ ] 4.8 Before merge, measure secrets false positives: run `secrets` on redacted copies of real notes in a scratch git repo outside every Mnemo repo; record only the hit count per pattern in the PR; delete the copies afterwards.

## 5. Save

- [ ] 5.1 Implement `save` in the order design.md gives; tests with `scenario: note-save / Clean save`, `/ Default message` and `/ Ignored file stays out` comments, using a scratch repo with a local bare remote.
- [ ] 5.2 Blocking tests with `scenario: note-save / Secret blocks the save` and `/ Broken link blocks the save` comments; each asserts no new commit and unchanged file bytes.
- [ ] 5.3 Conflict tests with `scenario: note-save / Remote edited the same note` and `/ Rebase left from an interrupted run` comments; each asserts the local edit survives and no rebase is in progress afterwards.
- [ ] 5.4 Push tests with `scenario: note-save / Push fails`, `/ Next save pushes the earlier commit` and `/ Nothing to do` comments, making the bare remote unreachable by renaming it.
- [ ] 5.5 Timeout test with a `scenario: note-save / Remote never answers` comment, using a remote command that sleeps past a time limit the test lowers.
- [ ] 5.6 manual: note-save / Credentials would be asked for: a unit test cannot stand up an authenticating remote; on a scratch clone of a private HTTPS repo with no credential helper, `save` must fail at once.

## 6. Docs

- [ ] 6.1 docs and spec map: `CLAUDE.md` (VERSION rule replaces the plugin.json rule; layout), `README.md` (no marketplace install; copy-and-refresh release), `cla.io/project-facts.md` (test command and the `tests/`, `evals/` locations; workspace shape); `plugins/mnemo/skills/README.md` moved by 1.1.
