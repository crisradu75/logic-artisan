# Dispatching lite-pr's reviewers

Read this from Review, before the dispatch. `SKILL.md` holds the diff-review sentence that goes in each prompt, the toolkit names and each reviewer's `model:`. The reviewer table and its models are in "Review sizing by risk" in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`, which owns them: this file copies none of it.

**The narrow agents.** Add `pr-test-analyzer` when tests change, and `type-design-analyzer` on a new invariant-bearing type, each routed per `model-routing.md`. An agent other than the three `pr-review-toolkit` reviewers keeps its own plugin's prefix (`plugin-dev:skill-reviewer`).

**Save the diff first.** Save the diff to a file outside the working tree: the session scratchpad, or when none is listed a `mktemp` file passed as a native path (`cygpath -w` in Git Bash on Windows). Delete it when the round ends.

**Launch them in parallel in one message.** Pass each reviewer the diff described by file and symbol plus the absolute path of its diff file, not the raw diff pasted inline.

**Ask each reviewer for the report shape** in slot 4 of `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/subagent-brief.md`: on a diff the caller judges to touch a protected area, the per-hunk `path:line — verdict` list before the findings.
