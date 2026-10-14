# TODO

Leftover review suggestions (lite-pr, spec/code mismatch rule):

- Quote the new `rules.specs` mismatch rule in `openspec/config.yaml` and the `cla-setup` seed, like its neighbours, so a later colon cannot break the YAML.
- Consider naming an example for "blocked outside the repo" (for example an upstream tool).

Leftover review suggestions (spec-proof-checker):

- In per-scenario mode, a requirement with no `#### Scenario:` adds no unit, so `check_spec_proof.py` never checks it; report a requirement that has zero scenarios.
- An unclosed code fence in a spec hides the rest of the file from `check_spec_proof.py` (it errors only when no spec parses at all); report an unclosed fence per file.
- `manual: <heading>: <reason>` names a heading, not a spec, so one line covers a same-named changed requirement in every spec of a touched change. Fixing it needs a format change to the tasks rule; the limit is documented in the script docstring.

Leftover review suggestions (mutation opt-in):

- `test_mutation_batch_is_opt_in.py` batch-rule test looks back a fixed 60 characters for its "When a batch is run" prefix; anchoring on the bullet start would be tighter.
