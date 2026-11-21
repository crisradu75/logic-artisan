# Implement post-checks

Read by Implement step 4 of `SKILL.md`. A tick does not read the claim under it, so run these as well as the ticked-and-ready count.

- **A ticked task that names a test is checked for that test** — a quoted test name, a `Test:` clause or a test file. Grep the tree for it; a miss is a Handoff Issue, and the test is written inline before leaving Implement. Each requirement a change adds or modifies has such a task, whose test carries a `requirement: <spec> / <heading>` comment line, or a tasks.md line `manual: <spec> / <heading>: <reason>` — this check is what ties a requirement to its proof. Put that comment line above any test you write.
- **Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/check_spec_proof.py`** (read-only; a repo with `openspec/` only). Each `PROBLEM` line it prints is a Handoff Issue; exit 2 means it could not run (a malformed facts line, no specs), also an Issue.
- **A task asserting a measurement records the value inline**: `- [x] 4.2 … measured: 1158 passed, 1 skipped`. The tick is not the evidence; the number is.
- **Re-measure a 2–3 task sample** of the measurement- or test-bearing tasks yourself.

A task is `[ ]` until it is done; prose under a ticked box saying "NOT DONE" makes every count wrong. A task completable only by running the *built* tool, or blocked on an external deploy, is not an Implement miss: record it as `deferred-to-TODO` at Propose and treat it as ✓-with-deferral here.
