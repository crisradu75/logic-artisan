# TODO

Leftover review suggestions (spec-proof-checker):

- `manual: <heading>: <reason>` names a heading, not a spec, so one line covers a same-named changed requirement in every spec of a touched change. Fixing it needs a format change to the tasks rule; the limit is documented in the script docstring.

Leftover review suggestions (cla-setup single-pass rules comparison):

- The key line test `/^  [a-z].*:$/` in the awk pass, like the shell `case` it replaced, reads `[a-z]` under the current locale; pin `LC_ALL=C` on the awk call if a locale ever matches capitals. (The edit is in the awk pass of `cla-setup/SKILL.md`.)
