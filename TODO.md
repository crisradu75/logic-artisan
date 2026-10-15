# TODO

Leftover review suggestions (spec-proof-checker):

- `manual: <heading>: <reason>` names a heading, not a spec, so one line covers a same-named changed requirement in every spec of a touched change. Fixing it needs a format change to the tasks rule; the limit is documented in the script docstring.

Leftover review suggestions (cla-setup single-pass rules comparison):

- The key line test `/^  [a-z].*:$/` in the awk pass, like the shell `case` it replaced, reads `[a-z]` under the current locale. Checked 2026-10-15: not reproduced. GNU Awk 5.4.0 (Git for Windows) matched `  foo:` and never `  Foo:` under all 766 locales `locale -a` lists. The shipped heredocs have no capital-initial key line, and rule lines start with four spaces, so they cannot match the test. Older gawk on older glibc may match capitals (from memory, not tested here); mawk and BSD awk are believed to compare bytes. Pin `LC_ALL=C` only if a real report shows it. (The test is in the awk pass of `cla-setup/SKILL.md`.)

Leftover review suggestions (spec-proof empty check (sweep PR)):

- A live spec with several scenario-less requirements gets only the generic 'no scenario parsed' line. Per-requirement headings should appear too; the generic line is pinned at `plugin-tests/tests/skills/_shared/test_check_spec_proof.py:1010`.
- `_bullet_start` in `plugin-tests/tests/consistency/test_mutation_batch_is_opt_in.py` counts any spaced hyphen as a bullet start. It should match only a real list marker.

Leftover review suggestions (spec-writing rules):

- In the one-outcome rule, reword 'supporting SHALL clause' to 'one SHALL per requirement; a second SHALL is a second outcome'. The rule is in `openspec/config.yaml:24` and its mirror in `.claude/plugins/cla/skills/cla-setup/SKILL.md:141`.
- The configurable-values rule's 'as configured' is vague; say the key's exact name as it appears in the config file. The rule is at `openspec/config.yaml:27` and `.claude/plugins/cla/skills/cla-setup/SKILL.md:144`.

Leftover review suggestions (orchestration economy rules):

- Rule 12 in `orchestration-economy.md` could name `gh pr view` as the check, since an agent's report can be stale.
- Rule 8 could say its scratch folder should be gitignored, so rule 7's debris check stays quiet. The repo's `.gitignore` has no scratchpad entry today.
