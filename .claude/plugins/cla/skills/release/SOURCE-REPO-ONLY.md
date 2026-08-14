# Source-repo-only scope

This scope asserts facts about the CANONICAL repo's own source — the repo-root
`.claude-plugin/marketplace.json` catalog, and `CLAUDE.md`'s `**Current release:**`
line. A consuming repo has neither: it receives the `release` skill with the
plugin but does not own the catalog that publishes it, and its own `CLAUDE.md` is
about its own project.

`run_tests.py` therefore skips this scope, with a visible SKIP row, in any repo
that is not the canonical source. The skill itself remains fully usable — only
its preconditions-about-this-repo tests are source-only.

Deleting this file re-arms the scope everywhere — do that only if every assertion
inside becomes portable.
