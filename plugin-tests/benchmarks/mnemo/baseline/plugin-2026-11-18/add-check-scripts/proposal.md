# Proposal

Budget: protected

## Why

Nothing yet enforces that a note reaching `main` is valid and free of secrets, or that a capture is saved before a cloud VM is reclaimed. The owner decided the shape (architecture Q1, Q4, Q9 except the trigger evals, Q10, Q12–Q14; structure Q3, Q6 except `evals/`, Q7, Q8, Q13, Q14 and "Scaffold spec requirements" in `cla.io/decisions/mnemo-benchmark-batch-2026-11-18.md`). This first implementation change also retires the plugin packaging that nothing reads any more (Q14).

## What Changes

- **Layout (Q14, early task group):** create `mnemo-plugin/` and a root `VERSION`; move `plugins/mnemo/skills/README.md` to `mnemo-plugin/skills/README.md`; delete `.claude-plugin/marketplace.json`, `plugins/mnemo/.claude-plugin/plugin.json` and the empty `plugins/`; update `CLAUDE.md` and `cla.io/project-facts.md`, and make `README.md` and the facts file name only files that exist or mark the change that adds them. **BREAKING:** the `cris-mnemo` marketplace is gone.
- **Base schema** in `mnemo-plugin/mnemo/conventions/base-schema.yml` (structure Q7), add-only.
- **Check script** `mnemo-plugin/mnemo/scripts/mnemo_check.py`: `links`, `schema`, `deletions`, `secrets`, `save`, on changed files only (structure Q13). It reads the YAML subset of architecture Q4.
- **Tests** at the repo root in `tests/` (`unittest`, standard library): shipped layout, `VERSION` equals tag, stdlib-only.
- Out of scope: hook scripts and wiring, the Python probe, the guard's command-form tests, the live device test, and the hook exit-code and timeout tests (the hooks change); `mnemo-setup`, its copy map and the stamp-equals-tag test (`mnemo-setup`); `mnemo-improve` and the deferred metadata (`add-mnemo-improve`); the 20 trigger prompts, their `claude -p` runner, the 18-of-20 pass mark and `evals/` (architecture Q9, structure Q6; Open question 10).

## Capabilities

### New Capabilities
- `note-checks`: the four checks, which files are notes, their exit statuses, the base schema and the YAML subset.
- `note-save`: the one-call check, commit and push.
- `shared-files-release`: what `mnemo-plugin/` may hold and `VERSION` against tags.

### Modified Capabilities
None.

## Impact

New `mnemo-plugin/`, `VERSION`, `tests/`, `.gitattributes`. Removed packaging manifests. No domain repo changes until `mnemo-setup` copies a tag. See `design.md` for the save order and the secret patterns.

## Risks noted

- Two saves at once (capture and the Stop hook) collide on git's lock; the second reports "cannot run" and the next turn retries.
- The secrets check fires on long order numbers or timestamps; the owner-run false-positive measurement sizes it before merge.
- A domain whose Python is older than 3.8 cannot run the script; the hooks change owns that message.

## Open questions

1. **Save order vs Q13.** Q13 orders save as pull, check, commit, push. Committing first would keep each capture as a commit even when the pull conflicts. Recommend: keep Q13's order, as specified; owner may switch to commit-first.
2. **Q13's Stop-hook early exit vs Q12 "push right away".** Q13 says the Stop hook exits 0 when `git status --porcelain` is empty, so a commit whose push failed is never retried by the hook, against Q12. `README.md` already says the hook runs `save` when a commit waits, which contradicts Q13. `save` itself pushes a waiting commit (specified), but the hook is the hooks change's, and that change (`add-guard-hooks`, named in `README.md`) is not proposed yet. Recommend: the owner amends Q13 so the hook also runs when a commit waits, and confirms the hooks change is planned with `save`'s 90-second limit and exit 4.
3. **Exit statuses** (decisions silent): recommend 0 pass, 1 note problem, 2 cannot run, 3 secret found, 4 committed but not pushed.
4. **Which files are notes** (silent): specified as every `.md` file outside `.claude/`, `_meta/`, `sources/` and `attachments/`, except top-level `CLAUDE.md`, `AGENTS.md` and `README.md`; `secrets` still scans every changed file. Owner to confirm.
5. **Link syntax** (silent): recommend Markdown links to relative paths only. URLs, anchors and `[[wikilinks]]` are not checked.
6. **Masked secrets vs checksums.** "Masked or not" rules out checksum validation, which would cut false positives. Recommend: no checksums, as decided; revisit after the measurement.
7. **Binary files and secrets** (silent). Specified: every changed file is scanned as text, so no file is skipped. The card pattern then matches PDF cross-reference lines, SHA-256 hex in the stamp file and two adjacent ISO dates; a hit never falls back to `inbox/` (Q8), so a capture with a PDF could never be saved. Recommend: the owner-run measurement covers attachments and a stamp file, and the owner decides between skipping binary files and exempting known formats before the table is switched on.
8. **Shipped-file list before the copy map exists:** recommend the layout test allows the fixed folder shape, minus `skills/mnemo-setup/`; `mnemo-setup` later makes its copy map the source.
9. **First `VERSION`** (silent): recommend `0.2.0`, after `plugin.json`'s `0.1.1`.
10. **Trigger prompts and evals unowned** (architecture Q9, structure Q6). No proposed change builds the 20 prompts, the runner or the pass mark. Recommend: a separate evals change once the first skill exists.
11. **Push target and waiting commits** (silent). Specified: a branch with no upstream pushes to the same name on `origin`, and waiting commits are scanned for secrets only before a push. Owner to confirm.
