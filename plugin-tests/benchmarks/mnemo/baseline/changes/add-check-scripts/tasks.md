# Tasks

Owner-on-device tasks are marked **[owner, device]**. Every other task runs in an agent session on this machine.

## 1. Verify first (gates later groups)

- [ ] 1.1 **[owner, device]** Check that `${CLAUDE_PLUGIN_ROOT}` is expanded inside `SKILL.md` text, with a scratch plugin skill that prints it, in desktop Claude Code and in one cloud session. Record the result here. Gates 4.1. If it is not expanded, use structure Q3's fallback, a shared non-user-invocable skill.
- [ ] 1.2 Check that `claude plugin eval` fits the trigger tests (20 prompts, pass mark 18 of 20), and find where it expects its prompt file. Record the evals folder path for 9.3. Create no eval files.
- [ ] 1.3 Check that `claude plugin validate .` accepts a `git-subdir` source with a tag `ref`. Use a scratch copy of `marketplace.json`. Gates 8.2.
- [ ] 1.4 **[owner, device]** Check that claude.ai plugin sync installs the plugin from a tagged `ref`: add a test marketplace at **Customize > Plugins** and open one cloud session. Gates 8.2.
- [ ] 1.5 **[owner]** Supply redacted copies of any personal notes you keep today, or confirm there are none. Gates 1.6.
- [ ] 1.6 Build the stand-in corpus for the real-file checks. No domain repo exists yet, so it holds read-only copies, in `scratchpad/add-check-scripts/corpus/`, of:
  - the files from 1.5
  - Markdown files with YAML front matter from the owner's other local repos (research reports, CLA skill files)

  Never commit the corpus. `measured:` gives the file count.

## 2. Test harness

- [ ] 2.1 Add `tests/` at the repo root, with a helper that builds a temporary domain repo, a bare local remote and a fixed git identity. The helper runs the script through `sys.executable`. Done when `python -m unittest discover -s tests` exits 0.

## 3. Check interface

- [ ] 3.1 Add the `plugins/mnemo/scripts/mnemo_check.py` entry point with the five subcommands. Tests carry `scenario: check-interface / Help lists the five subcommands` and `/ No index subcommand`.
- [ ] 3.2 Implement exit codes 0, 1 and 2, the one-line stderr problem format, and the stdout summary from design D2. Tests carry `scenario: check-interface / <heading>` for each scenario under Exit status and Problem messages.
- [ ] 3.3 Make a check that cannot run exit 2 and never print a pass. Tests carry `scenario: check-interface / Not a Mnemo repo` and `/ Git fails`.
- [ ] 3.4 Resolve the repo root with `git rev-parse --show-toplevel` from the working directory. Tests carry `scenario: check-interface / Run from a subfolder` and `/ Run outside a git repo`.
- [ ] 3.5 Implement the default, `--staged`, `--range` and `--all` selections from design D4. Tests cover the three Changed-files scenarios, an empty selection (exit 0) and a repo with no commits.
- [ ] 3.6 Implement the note definition. Tests carry `scenario: check-interface / A file in a type folder is a note` and `/ Top-level and underscore files are not notes`.

## 4. Base schema and the `schema` check

- [ ] 4.1 After 1.1, add `plugins/mnemo/conventions/base-schema.yml` as in design D6. Test carries `scenario: note-schema / Required set is fixed`.
- [ ] 4.2 Implement the YAML subset reader from design D5. Tests carry `scenario: note-schema / <heading>` for the three YAML-subset scenarios, plus one unit case for each D5 row.
- [ ] 4.3 Report missing or empty required base fields. Tests carry `scenario: note-schema / Missing summary` and `/ Empty title`.
- [ ] 4.4 Accept notes that leave out optional fields or carry extra fields. Tests carry `scenario: note-schema / Optional fields left out` and `/ Extra field`.
- [ ] 4.5 Check the date, list and status values. Tests carry `scenario: note-schema / <heading>` for the three Base-field-values scenarios.
- [ ] 4.6 Apply the inbox rules. Tests carry `scenario: note-schema / Unclassified note in the inbox` and `/ Wrong status in the inbox`.
- [ ] 4.7 Read `mnemo.schema.yml` as in design D7. Tests carry `scenario: note-schema / <heading>` for the three Domain-schema-file scenarios.
- [ ] 4.8 Apply the domain type rules and the name-pattern tokens. Tests carry `scenario: note-schema / <heading>` for the three Domain-type-rules scenarios, plus one case per token.
- [ ] 4.9 Real-file check: run the `schema` reader read-only over the corpus copies. Done when there is no traceback and every rejection names a file and a line. `measured:` gives the rejection counts by rule.

## 5. Links and deletions

- [ ] 5.1 Implement the `links` check as in design D8. Tests carry `scenario: note-checks / <heading>` for the three Links-resolve scenarios.
- [ ] 5.2 Report the files that link to deleted or moved paths. Tests carry `scenario: note-checks / Unchanged note links to a deleted note` and `/ Move with updated links`.
- [ ] 5.3 Implement the `deletions` check. Tests carry `scenario: note-checks / <heading>` for the three Deletions scenarios.
- [ ] 5.4 Real-file check: run the link extractor read-only over the corpus copies. Done when there is no traceback. `measured:` gives the link count and the unresolved count.

## 6. Secrets

- [ ] 6.1 Implement the patterns from design D9 with invented values. Tests carry `scenario: note-checks / Card number`, `/ Private key` and `/ Number that fails the checksum`.
- [ ] 6.2 Count masked values as hits. Tests carry `scenario: note-checks / Masked card number` and `/ Redacted placeholder`.
- [ ] 6.3 Never print matched values. Test carries `scenario: note-checks / Report hides the value`.
- [ ] 6.4 Scan every commit in a `--range`. Test carries `scenario: note-checks / Secret added then removed`.
- [ ] 6.5 Cover `inbox` notes in the secret scan. Test carries `scenario: note-schema / Secret scan still covers the inbox`.
- [ ] 6.6 Measure false positives on the corpus before 7.1 turns on blocking. Done when there are zero unexplained hits. Fix each false hit by tightening its pattern, with a regression test. `measured:` gives the hits by kind.

## 7. `save`

- [ ] 7.1 Implement `save` as in design D10. Tests carry `scenario: note-saving / Clean save` and `/ Remote moved ahead`.
- [ ] 7.2 Exit early when there is nothing to save. Test carries `scenario: note-saving / Clean working tree` and asserts that no git network command ran.
- [ ] 7.3 Commit nothing when a check fails. Tests carry `scenario: note-saving / Secret blocks the save` and `/ Check cannot run`.
- [ ] 7.4 Stage named paths only, and never use `git add -A`. Tests carry `scenario: note-saving / One of two changed notes` and `/ Already-staged file left out`.
- [ ] 7.5 Retry the push once, then exit 3. Tests carry `scenario: note-saving / Remote moved during the save` and `/ Remote unreachable`.
- [ ] 7.6 Abort the rebase on a conflict. Test carries `scenario: note-saving / Same line changed on both sides`.
- [ ] 7.7 Add the `MNEMO_NET_TIMEOUT_SECONDS` limit and the `SAVE_WORST_CASE_SECONDS` constant. Test carries `scenario: note-saving / Remote never answers`. A second test asserts the constant is at least 4 times the default limit plus 30.

## 8. Release and packaging

- [ ] 8.1 **[owner]** After 1.3 and 1.4, cut tag `mnemo--v0.1.1` on the `main` commit whose manifest says `0.1.1`. Cut it from the Mac or GitHub's web page, and never move it afterwards.
- [ ] 8.2 Switch `.claude-plugin/marketplace.json` to the `git-subdir` pointer from design D11. Done when `claude plugin validate .` passes.
- [ ] 8.3 Add the release-pointer tests. Tests carry `scenario: plugin-release / <heading>` for the three Release-pointer scenarios and `/ Branch behind the pointer`.
- [ ] 8.4 Add the packaged-path test. Tests carry `scenario: plugin-release / Missing referenced file` and `/ Scanner finds references`.
- [ ] 8.5 Add the packaging tests. Tests carry `scenario: plugin-release / Test file inside the plugin`, `/ Third-party import` and `/ Workflow added`.
- [ ] 8.6 Add the shared-file tests. Tests carry `scenario: plugin-release / Second copy of the base schema` and `/ Second script beside the check command`.
- [ ] 8.7 Bump `plugins/mnemo/.claude-plugin/plugin.json` to `0.2.0`. Done when `claude plugin validate plugins/mnemo` passes.

## 9. Integration

- [ ] 9.1 Save `git status --porcelain --ignored --untracked-files=all` outside the repo. Then run `python -m unittest discover -s tests` once on the final commit and diff the status again. Done when the suite passes and the diff shows no new lines outside `scratchpad/`.
- [ ] 9.2 `manual: No note content: confirm by reading that every fixture and example uses invented placeholders, as the repo rules require.`
- [ ] 9.3 docs and spec map: `README.md` (layout rows for `conventions/`, `scripts/` and `tests/`, the test command, and the tag form), `CLAUDE.md` (release and test rules), and `cla.io/project-facts.md` (test command, test locations, and the evals path from 1.2). None affected: `plugins/mnemo/skills/README.md`, because no skill changes.

## Workflow follow-up

- `add-guard-hooks` sets the `hooks.json` timeout to at least `SAVE_WORST_CASE_SECONDS`, and must check that Python 3 is present in the cloud VM before its fail-closed commit hook ships.
- Re-run 4.9, 5.4 and 6.6 on redacted copies from the first real domain repo once `mnemo-setup` creates one.
