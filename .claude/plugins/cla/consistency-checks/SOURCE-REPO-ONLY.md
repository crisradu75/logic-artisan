# Source-repo-only scope

This scope asserts facts about the CANONICAL repo's own source — cross-scope drift checks, the curated token list, doc-fact counts, an installed pre-push hook. A
consuming repo receives this directory with the plugin (the marketplace ships
the whole tree) but cannot satisfy those assertions and did not cause their
failures.

`run_tests.py` therefore skips this scope, with a visible SKIP row, in any repo
that is not the canonical source. Deleting this file re-arms the scope
everywhere — do that only if every assertion inside becomes portable.
