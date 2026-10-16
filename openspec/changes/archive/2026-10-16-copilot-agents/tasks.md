# Tasks

## 1. Primary sources

- [x] 1.1 Read the raw docs for custom-agent frontmatter, tool aliases, the plugin reference's agent location and the Agent Plugins 1.0 spec; record each field's URL in the PR body. Done when no field in a copy lacks a cited page.

## 2. The copies

- [x] 2.1 Add the dev script that writes each Copilot copy from its Claude agent and refuses an unmapped tool, model or field; generate the five. Test that a copy equals the render and an unmapped input raises. Carry `requirement: plugin-distribution / Helper agents in GitHub Copilot CLI`.
- [x] 2.2 Test that each copy keeps its agent's instructions and description, none is missing or orphaned, and each grants only `read` and `search`. Same requirement comment. Done when editing one Claude agent's body fails the suite.
- [x] 2.3 Allow the Copilot agent copies in the shipped-tree check (a sixteenth pattern with its reason, cap raised in the same commit); test that stray neighbours are refused. Carry `requirement: plugin-distribution / What a release contains`.

## 3. Checks

- [x] 3.1 The Claude install is unchanged: `claude plugin validate` passes on the plugin and the catalog, and a `claude -p --plugin-dir` run lists the same 5 `cla:` agents. measured: validate exit 0 before and after; 22 agents and 66 skills listed on both trees.
- [ ] 3.2 Run `pytest plugin-tests -q -n auto --dist loadfile` and `openspec validate --specs --strict`, once each on the final commit.

## 4. Docs

- [x] 4.1 docs and spec map: README, plugin README, DEVELOPER-GUIDE, the root manifest description and the decisions file updated (agents offered, guard hooks do not run in Copilot, untested); none affected: the spec map is not in this repo's doc list.
