---
name: report-upstream
description: "Report a defect or gap in the cla plugin's own portable core back to the canonical source repo as a GitHub issue. Use when working in a repo that consumes the plugin and you find something wrong in a synced skill, agent, hook, or script — something that would be wrong in every repo running it, not just this one. Triggers on /cla:report-upstream or natural language like 'this hook is broken upstream', 'report this to the cla source', 'file this against the plugin', 'that's a bug in the harness itself'."
argument-hint: "[what is wrong | (empty — infer from the conversation)]"
allowed-tools: Bash, Read, Grep, Glob, AskUserQuestion
---

# /cla:report-upstream — send a core defect back to the canonical source

The plugin is installed read-only from a marketplace, so a repo that finds a defect in
portable core cannot fix it where it lives. Without a channel back, the observation dies
with the session and the same defect is rediagnosed independently in every repo running
the plugin — which is exactly what happened before this existed: one launcher bug was
diagnosed and fixed separately in three repos, and none of those fixes reached the others.

This skill moves **prose, not code**. It opens an issue; a human upstream decides.

## The admission test — apply it before anything else

> If the canonical source adopted this change, would **every** repo running the plugin be
> better off?

- **Yes → report it.** A guard hook that no-ops on a platform. A script that mishandles a
  line ending. A skill step that is wrong everywhere, not just here.
- **No → report nothing, and change nothing.** It is legitimate local adaptation and
  belongs in this repo's own overlay (`cla.io/overlays/<skill>.md`). Say so and stop —
  a channel that carries local preferences upstream stops being read.

If the answer is genuinely unclear, ask the user rather than guessing. A wrong "yes" costs
a maintainer's triage; a wrong "no" costs every repo the fix.

## 1. Establish the facts before writing anything

**Read the actual core file** in the installed plugin and quote what is wrong. An issue
whose claim cannot be checked against a line of source is not actionable.

State a claim about the current core only if you verified it **this run**. The recurring
failure in the file-based predecessor of this channel was an item asserting "unfixed
upstream" that had been fixed long before.

Establish, in this order:

1. The **exact path** inside the plugin (`skills/<name>/…`, `hooks/…`, `lib/…`).
2. The **installed version** — read `version` from the plugin's own
   `.claude-plugin/plugin.json`. A report against an unnamed version cannot be triaged.
3. Whether the behaviour is **already fixed** in a newer release, if one is available.
4. Whether this repo has **local modifications** to that file. If it does, say so — the
   defect may be in the local edit rather than in core.

## 2. Resolve where the issue goes

The canonical source repo is a property of the PLUGIN, not of this repo, so it is not an
overlay fact. Read it from the plugin's own manifest:

```bash
# `repository` in .claude-plugin/plugin.json — the plugin declares its own origin
```

If the manifest carries no repository field, **stop and ask the user** for the target
rather than guessing a slug. Never hardcode one in this file: portable core must not name
a specific repository.

## 3. Check it is not already reported

The same defect resurfaces in every repo that hits it, so duplicates are the default
outcome, not an edge case:

```bash
gh issue list --repo <owner/repo> --search "<distinctive symbol or path>" --state all
```

An open issue matching → **add a comment** naming this repo's platform, version, and any
detail the original lacks. Do not open a second issue. A closed issue matching → say so and
ask the user whether this is a regression before opening anything.

## 4. Open the issue

Title: one line naming the defect and its location, specific enough to search for later.

Body — keep it tight; the reader has none of this session's context:

```markdown
**Path:** `<path inside the plugin>`
**Plugin version:** `<version from plugin.json>`
**Platform:** <OS + shell, when the defect is platform-specific — say "any" if not>

### What happens

<Concretely: what breaks or is missing, under what conditions, and who notices. Name the
platform or configuration if it only bites on some. For a gap rather than a defect, say
what core does not cover and what that costs.>

### Why it belongs in core

<The admission test, answered explicitly. What makes this generic rather than local.>

### Suggested fix

<Enough for a maintainer to act without rediscovering the problem: a diff, a symbol name,
or a precise description. Say so plainly if you only have a diagnosis and no fix.>
```

Open it with a body file, never an inline multi-line string:

```bash
gh issue create --repo <owner/repo> --title "<title>" --body-file <path>
```

Report the issue URL as the last line of output.

## What this skill will not do

Say these plainly rather than letting the user assume otherwise:

- **It does not fix anything.** Not here, not upstream. The local repo keeps whatever
  workaround it has; the issue is the deliverable.
- **It does not track resolution.** Nothing polls the issue or notices when it is fixed.
- **It cannot see a defect you have not read.** A report assembled from memory of a file
  rather than from the file is how "already fixed upstream" issues get filed.
