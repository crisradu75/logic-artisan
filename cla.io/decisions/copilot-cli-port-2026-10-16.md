# Copilot CLI port — 2026-10-16

**Topic:** making the CLA plugin installable from GitHub Copilot CLI. GitHub issue "Make the CLA
plugin installable from GitHub Copilot CLI" (#302).

**Grounding:** read-only research on 2026-10-15 from GitHub's Copilot docs and the
github/copilot-cli changelog (CL = https://raw.githubusercontent.com/github/copilot-cli/main/changelog.md).
`copilot` was not installed, so nothing was run against it. The research read WebFetch summaries,
not raw pages; re-read a page before building on a single claim.

## Decisions

1. **Scope:** Copilot CLI only. The docs state the Copilot app and cloud agent are untested.
2. **Manifest:** add Copilot's newer Agent Plugins 1.0 root `plugin.json` beside the Claude
   manifest, rather than relying on Copilot reading `.claude-plugin/plugin.json` as a legacy
   plugin. Consequences: the root manifest takes precedence over `.plugin/` and `.claude-plugin/`
   and may not carry component path fields (`extensions` is the client-specific slot); every
   release must keep it in step with `plugin.json` and `marketplace.json`, so the release-drift
   check covers it.

3. **Hooks (decided 2026-10-16: wait for a live test).** The guards stay Claude-only until someone
   installs Copilot CLI and checks how they behave. A Copilot `preToolUse` timeout always lets the
   command through, which would weaken a guard that is meant to block when it fails.
4. **Skill text (decided 2026-10-16: wait for a live test).** No per-client wording and no list of
   reduced features yet. Decide after the live test (step 1 below).

## What the research found

| Issue assumption | Verdict | Source |
|---|---|---|
| `.github/plugin/marketplace.json` is read | Holds; Copilot also reads `.claude-plugin/marketplace.json`, `.plugin/`, root `marketplace.json` | docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference |
| Copilot rejects `git-subdir` | Holds; not documented, not in CL | same |
| Source can be repo + subdirectory + ref | Holds: `{"source":"github","repo":"o/r","ref":"…","sha":"<40>","path":"…"}`; tag ref from 1.0.62 | same; CL 1.0.62, 1.0.70 |
| Both manifests in one directory | Holds; precedence partly unclear | cli-plugin-reference |
| Skills load | Holds; deduped by `name` | docs.github.com …/add-skills |
| Skills invoked as `/cla:<name>` | Unknown; CL 1.0.71 implies `/plugin:skill` | CL |
| Agents port | Mostly holds; `.agent.md` takes name, description, tools, model; `Read`/`Grep`/`Glob` accepted; unknown tools ignored | docs.github.com/en/copilot/reference/custom-agents-configuration |
| Hooks need translating; no `CLAUDE_PLUGIN_ROOT` | Partly wrong: plugin hooks get `CLAUDE_PLUGIN_ROOT`, `PLUGIN_ROOT`, `COPILOT_PLUGIN_ROOT` (CL 1.0.26); Claude-format `PreToolUse` fires with Claude matchers (CL 1.0.62); whether `permissionDecision:"ask"` is honoured is undocumented | docs.github.com …/hooks-reference |
| `preToolUse` fails closed | Mostly: exit 2, a crash or other non-zero exit denies; timeouts always fail open; exit 1 is ignored on other events | hooks-reference |
| No output-style equivalent | Holds; instructions come from `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`; plugin-shipped instructions undocumented | docs.github.com …/add-custom-instructions |

Claude-only surface in `.claude/plugins/cla/skills/` (grep counts, 2026-10-15): `AskUserQuestion`
43 lines in 21 files; Agent/SendMessage/EnterWorktree/Skill tool terms 83 lines in 24 files;
`${CLAUDE_PLUGIN_ROOT}` 216 lines in 56 files (substitution in a SKILL.md body is undocumented);
`/cla:` 233 lines in 53 files. Hooks: 4 entries in `hooks/hooks.json`, all through
`probe-python.sh`. Agents: 5 files with `tools: ["Read","Grep","Glob"]` and a `model:`.

## Draft split (ordered)

1. **Test install:** install CLA in a real Copilot CLI and answer each unknown above. Findings
   note only.
2. **Marketplace and root manifest:** `.github/plugin/marketplace.json` with a `github` source,
   plus the Agent Plugins 1.0 root `plugin.json`. Done when `marketplace add` and `browse` list CLA
   and the Claude install is unchanged.
3. **Release-drift check:** one check that `plugin.json`, the root manifest, both marketplace refs
   and the CLAUDE.md release line agree; extend `/release`.
4. **Skill portability:** after the docs-task change (#387) merges, since it edits `spec-to-pr`
   and `lite-pr`.
5. **Agent profile port.**
6. **Hook port:** one issue per guard, each with an allow and a deny test, fail-closed checked.
7. **Instructions stand-in and install docs.**
