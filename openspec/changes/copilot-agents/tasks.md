# Tasks

## 1. Primary sources

- [x] 1.1 Read the raw docs for custom-agent frontmatter, tool aliases, the plugin reference's agent location and the Agent Plugins 1.0 spec before building; record each field's URL in the PR body. Done when no field in a Copilot copy lacks a cited page.

## 2. The copies

- [x] 2.1 Add `plugin-tests/scripts/sync_copilot_agents.py` and generate the five copies; it refuses a tool, model or field with no documented mapping. Test that a copy equals the render of its Claude agent and that an unmapped input raises. Carry `requirement: plugin-distribution / Helper agents in GitHub Copilot CLI`.
- [x] 2.2 Test that each copy keeps its agent's instructions and description, that no copy is missing or orphaned, and that a copy grants only `read` and `search`. Carry the same requirement comment. Done when editing one Claude agent's body fails the suite.
- [x] 2.3 Allow `com.github.copilot/agents/<name>.agent.md` in the shipped-tree check (a sixteenth pattern with its reason, cap raised in the same commit); test that stray neighbours are refused. Carry `requirement: plugin-distribution / What a release contains`.

## 3. The Claude install is unchanged

- [x] 3.1 `claude plugin validate` on the plugin directory and the catalog passes before and after, and a `claude -p --plugin-dir` run lists the same five `cla:` agents with no copy loaded twice. measured: recorded in the commit message.

## 4. Docs

- [x] 4.1 docs and spec map: README, plugin README (layout) and DEVELOPER-GUIDE (layout, script table, rule story) say the agents are offered to Copilot, generated, and untested in a live Copilot CLI; the root manifest description says agents are offered; README and DEVELOPER-GUIDE say the guard hooks do not run in Copilot; the decisions file records hooks and skill text as waiting for a live test. The spec map is not in this repo's doc list, so none affected there.
- [ ] 4.2 Run `pytest plugin-tests -q -n auto --dist loadfile` and `openspec validate --specs --strict`, once each on the final commit.
