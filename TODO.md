# TODO

Leftover review suggestions (spec-proof-checker):

- `manual: <heading>: <reason>` names a heading, not a spec, so one line covers a same-named changed requirement in every spec of a touched change. Fixing it needs a format change to the tasks rule; the limit is documented in the script docstring.

Leftover review suggestions (Purpose note in the spec checker):

- A hard-wrapped `**Serves:**` line is not told apart from a paragraph break. Only the first Purpose line is the Serves line (`check_spec_proof.py:490`). A wrapped second line counts as a later sentence (`:498`).
- An unpaired backtick can hide a sentence break in `count_sentences`. The code-span mask needs a pair (`check_spec_proof.py:439`), so one stray backtick can pair with a later one.
- In other repos, notes repeat on every run for unchanged older specs. `purpose_notes` runs over every live spec, not only changed ones (`check_spec_proof.py:843`).
- `check_spec_proof.py` crashes on a cp1252 console when a printed line has non-ASCII text. The final `print` at `check_spec_proof.py:861` sets no encoding. This predates the Purpose note.
- The spec-proof spec has no requirement for the new `NOTE purpose:` behaviour. `openspec/specs/spec-proof/spec.md` does not mention it; the behaviour is in `check_spec_proof.py:475-505`.

Leftover review suggestions (spec-proof empty check (sweep PR)):

- A live spec with several scenario-less requirements gets only the generic 'no scenario parsed' line. Per-requirement headings should appear too; the generic line is pinned at `plugin-tests/tests/skills/_shared/test_check_spec_proof.py:1010`.
- `_bullet_start` in `plugin-tests/tests/consistency/test_mutation_batch_is_opt_in.py` counts any spaced hyphen as a bullet start. It should match only a real list marker.

Leftover review suggestions (spec-writing rules):

- In the one-outcome rule, reword 'supporting SHALL clause' to 'one SHALL per requirement; a second SHALL is a second outcome'. The rule is in `openspec/config.yaml:24` and its mirror in `.claude/plugins/cla/skills/cla-setup/SKILL.md:141`.
- The configurable-values rule's 'as configured' is vague; say the key's exact name as it appears in the config file. The rule is at `openspec/config.yaml:27` and `.claude/plugins/cla/skills/cla-setup/SKILL.md:144`.

Leftover review suggestions (orchestration economy rules):

- Rule 12 in `orchestration-economy.md` could name `gh pr view` as the check, since an agent's report can be stale.
- Rule 8 could say its scratch folder should be gitignored, so rule 7's debris check stays quiet. The repo's `.gitignore` has no scratchpad entry today.
