# Tasks

## 1. Primary sources

- [x] 1.1 Read GitHub's raw docs for the marketplace and Agent Plugins 1.0 manifest fields before building; record each field's source URL in the PR body. Done when no field in the two new files lacks a cited page.

## 2. The files

- [x] 2.1 Add `.github/plugin/marketplace.json` and the root `plugin.json`; test that the catalog's `cla` entry is a `github` source with this repo, the plugin path and the current tag, and that the manifest uses only the Agent Plugins 1.0 fields with a valid name. Carry the comment `requirement: plugin-distribution / Installing from GitHub Copilot CLI`.
- [x] 2.2 Show the Claude install is unchanged: `claude plugin validate` on the plugin directory and the catalog passes before and after, and a run with a differently named root manifest still loads the plugin as `cla`. measured: `claude plugin validate` passed on the plugin directory and the catalog before and after; a run with the root manifest renamed still listed the plugin as `cla` 2.1.0, with the same 19 skills and 5 `cla` agents as main.

## 3. Release set

- [x] 3.1 Extend the existing version-agreement test to the Copilot manifest and both catalogs' refs, beside the CLAUDE.md line. Carry `requirement: plugin-distribution / Publishing a release`. Done when changing any one of the five versions fails it.
- [x] 3.2 Allow the root manifest in the shipped-tree check (a fifteenth pattern with its reason, cap raised in the same commit); test that it is accepted and a stray root file is not. Carry `requirement: plugin-distribution / What a release contains`.
- [x] 3.3 Update `/release` and CLAUDE.md's release section to the five-file edit; the skill's own test names every file the procedure bumps.

## 4. Docs

- [x] 4.1 README install section: the two Copilot commands, "Copilot CLI only", "untested in a live Copilot CLI", and what the manifest offers (skills). Test that the README says so. DEVELOPER-GUIDE release history and rule story updated.
- [ ] 4.2 Run `pytest plugin-tests -q -n auto --dist loadfile`, `openspec validate --specs --strict`, then `pytest plugin-tests -q`, once each on the final commit.
