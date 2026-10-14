# TODO

Leftover review suggestions (spec-proof-checker):

- `manual: <heading>: <reason>` names a heading, not a spec, so one line covers a same-named changed requirement in every spec of a touched change. Fixing it needs a format change to the tasks rule; the limit is documented in the script docstring.

Leftover review suggestions (spec-proof empty/fence checks):

- `test_mutation_batch_is_opt_in.py` batch-rule test: `rfind("- **", 0, at)` takes the nearest earlier bold bullet without checking that no plain bullet sits between it and the rule; stop the lookback at the nearest bullet start and require that one to be bold.
- In scenario mode a live spec whose only requirement has no scenario gets two `empty` lines for one cause (no unit parsed, and the requirement has no scenario); harmless noise.
