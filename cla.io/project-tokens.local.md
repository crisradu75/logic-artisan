# project tokens — this repo's own vocabulary, never to appear in synced core

Read as data by `.claude/plugins/cla/skills/_shared/scripts/check_no_project_tokens.py` (its unit and
CLI tests live at `plugin-tests/tests/conformance/test_no_project_tokens.py`, in this repo's own dev
tree — `extract-dev-tree-from-plugin` moved the tests out of the published plugin). One
token per `- ` bullet; an inline
`# comment` and surrounding backticks are stripped. This file is a `*.local.md` overlay living in
the repo's own `cla.io/` tree, outside the distributed plugin directory — each repo curates its own.

## Why the source repo needs one at all

The guard's own header used to reason that the token-list model "only fits a CONSUMING repo…
In the SOURCE repo it inverts — there are no local product tokens to protect." That is half
right, and the half it got wrong shipped six leaks.

It conflated two different lists:

- **Names of *other* repos** — genuinely open-ended, externally determined, and stale the
  moment a new project starts. Listing those means enumerating every repo the author works
  in, and it only ever catches names already known and therefore already fixed. That
  objection stands, and is why the list-free absolute-path guard exists.
- **This repo's *own* name and systems** — closed, finite, and self-known, exactly like a
  consuming repo's own vocabulary. The source repo does know what it is called.

Only the second list is here. A source-side token in portable core is worse than a
consuming-side one, because it reads as a fact about the *destination* the moment it syncs:
`discover_tests.py`'s "this repo has no root `package.json`" was true where it was written
and false in the next JS consumer.

<!--
Deliberately NOT listed, with the reason, so the next person does not re-add them:
  - cla / CLA          the plugin's own name; it is supposed to appear in its own core
  - openspec           a real dependency every consumer shares, not a local fact
  - claude-plugins     a consuming repo. Listed only for `market-distiller-mcp` below,
                       which broke that repo's guard on arrival; the general case is the
                       open-ended list the header argues against.
-->

- `logic-artisan`  # this repo — the canonical source. Write "the canonical source repo".
- `vv-harness`  # a source-side system with no analogue in a consuming repo
- `market-distiller-mcp`  # a consuming repo named in core; it failed that repo's own guard on arrival
