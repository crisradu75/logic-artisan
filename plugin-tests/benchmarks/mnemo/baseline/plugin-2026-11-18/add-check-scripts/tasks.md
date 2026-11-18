# Tasks

Every test builds its own scratch repo in a temporary folder with invented notes. No task reads or writes a domain repo. Each test below carries the `scenario: <spec> / <heading>` comment line for every heading it names.

## 0. Owner-run gate (outside what apply can tick; the change does not merge before it is recorded)

- [ ] 0.1 The owner measures false positives of the secret patterns, and runs the YAML-subset reader and `schema`, on redacted copies of their notes, their attachments (PDFs included) and a stamp-like file of SHA-256 hashes, outside this repo. Record only counts per pattern and per reader error in the PR; no note text in the diff. Proposal Open question 7 is settled before the table is switched on.

## 1. Layout (architecture Q14) and test harness

- [ ] 1.1 Create `mnemo-plugin/mnemo/scripts/`, `mnemo-plugin/mnemo/conventions/` and `mnemo-plugin/skills/`; `git mv` `plugins/mnemo/skills/README.md` to `mnemo-plugin/skills/README.md`, and reword it so `mnemo-setup` is not a copied skill. Check: `git status` shows a rename.
- [ ] 1.2 Delete `.claude-plugin/marketplace.json`, `plugins/mnemo/.claude-plugin/plugin.json` and the then-empty `plugins/` and `.claude-plugin/`. Check: `git ls-files plugins .claude-plugin` prints nothing.
- [ ] 1.3 Add the root `VERSION` holding `0.2.0` (proposal Open question 9). Check: the file is one line matching semver.
- [ ] 1.4 Update `CLAUDE.md`: a plain source repo, not a marketplace; replace the `plugin.json` bump rule with "bump `VERSION` in every PR that changes `mnemo-plugin/` or `mnemo-setup`; a published tag is never moved". Check: `grep -n plugin.json CLAUDE.md` prints nothing.
- [ ] 1.5 Make `cla.io/project-facts.md` and `README.md` name only paths that exist when this change ends, marking each later path (hook tests, `evals/`, `mnemo-setup`, `add-guard-hooks`) as planned with the change that adds it. Check: `check_fact_paths.py` passes, and every unmarked path in README's tables exists.
- [ ] 1.6 Add `tests/helpers.py` with a scratch-repo builder (temporary folder, invented notes, a bare repo as remote) that calls the script through `sys.executable`. Add `.gitattributes` with `*.sh text eol=lf`. Check: `python -m unittest discover -s tests` runs.

## 2. Base schema and checks

- [ ] 2.1 Write `base-schema.yml` (`required` and `optional` lists) and the YAML-subset reader. Tests for note-checks: "Value holding a colon", "Quoted list item holding a comma", "Outside the subset", "Field removed", "Optional field added", "Extra top-level key"; the base-field test asserts the nine fields are a subset, not the whole list.
- [ ] 2.2 Add changed-file selection (existing files only; deletions apart), the notes definition, repo resolution and the exit-status priority 2, then 3, then 1. Check: tested by 2.3 to 2.6.
- [ ] 2.3 Add `links` and `deletions`. Tests for note-checks: "Missing target", "Web link", "Unchanged note links to a deleted note", "Nothing deleted", "Unchanged note is not checked".
- [ ] 2.4 Add `schema`. Tests for note-checks: "Missing summary", "Optional fields absent", "Unknown type", "Inbox note without a type rule", "Note problem", "Named path is checked", "Raw source not a note", "Conventions file not a note".
- [ ] 2.5 Add `secrets` with the `design.md` pattern table. Tests for note-checks: "IBAN in an inbox note", "Masked card number", "Clean note", "Secret found"; plus one test per table row with invented values.
- [ ] 2.6 Tests across all four checks, git read with optional locks off. Tests for note-checks: "Not a Mnemo repo", "Unreadable file", "Run from a subfolder", "Script lives elsewhere", "Deleted note not read", "Repo unchanged after checks".

## 3. Save

- [ ] 3.1 Add `save` with `--message`, the default `save: <n> files` message, the no-network clean exit and the push target. Tests for note-save: "Changed notes saved", "Only an unpushed commit", "Nothing to do" (remote URL unreachable, still exits 0); plus a default-message test.
- [ ] 3.2 Stage the collected paths, check the staged blobs, restore the index on failure. Tests for note-save: "Secret in a capture", "Broken link", "Ignored file left out", "Committed bytes match" (the test rewrites the note between check and commit), "Deletion saved".
- [ ] 3.3 Fetch, overlap check and rebase, restoring the pre-run state on any conflict. Tests for note-save: "Same note changed elsewhere", "Waiting commit conflicts"; each asserts byte-identical notes and no rebase folder.
- [ ] 3.4 Add the unfinished-state refusal. Tests for note-save: "Rebase in progress", "Leftover lock".
- [ ] 3.5 Add the committed-not-pushed notice. Tests for note-save: "Remote unreachable", "Next run pushes".
- [ ] 3.6 Scan lines added by waiting commits before the push. Tests for note-save: "Secret in a waiting commit", "Secret added then removed".
- [ ] 3.7 Add the 30-second network limits, the disabled prompts and the removal of run-created lock files. Tests for note-save: "Silent remote", "Remote asks for a password"; each asserts the elapsed time and intact notes.

## 4. Shared files and release

- [ ] 4.1 Add `tests/test_shipped_layout.py`. Tests for shared-files-release: "Stray test file", "Per-domain file", "Setup skill in the shared folder", "Missing script", "Existing script", "Per-domain stamp named". Check: `python -m unittest tests.test_shipped_layout` passes on the real tree.
- [ ] 4.2 Add the version test, run against tags in scratch repos and against this repo's own tags. Tests for shared-files-release: "Tag and file agree", "Tag and file differ".
- [ ] 4.3 Add the stdlib and Python 3.8 test, using the standard-library module list and a 3.8 parse. Tests for shared-files-release: "Third-party import", "Newer syntax".
- [ ] 4.4 Run the full suite. Check: every test uses only scratch repos in a temporary folder, never a domain repo or the owner's notes; none skips for lack of a domain repo; afterwards `git status --porcelain --ignored --untracked-files=all` shows no new line except interpreter caches beside tracked scripts.

## 5. Docs

- [ ] 5.1 docs and spec map: `CLAUDE.md`, `cla.io/project-facts.md`, `mnemo-plugin/skills/README.md` (group 1); `README.md` checked against the exit statuses, `save` behaviour and existing paths, and updated where it differs.
