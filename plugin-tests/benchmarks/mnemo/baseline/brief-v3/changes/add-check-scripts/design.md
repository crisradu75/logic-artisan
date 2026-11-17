# Design

Triggers: security (the secret patterns decide what may reach GitHub history) and a new data model (the base schema, the schema grammar, and which files count as changed).

## Context

The repo today is a plugin marketplace with no code. Architecture Q12–Q14 turn it into a plain source repo whose `mnemo-plugin/` is copied into each domain repo's `.claude/`. The script below is the first file in that folder.

## Goals / Non-Goals

**Goals:** a single stdlib script that every later hook and skill calls; tests that hold the shipped folder and the version.

**Non-Goals:** the Python probe, hook wiring, skills, and setup's stamp file.

## Decisions

### Which files are notes
A note is any `.md` file outside `.claude/`, `_meta/` and `openspec/`, other than the top-level `CLAUDE.md`, `AGENTS.md` and `README.md`. Frontmatter is the block between a first line `---` and the next `---`.
- Rejected: every `.md` file. `_meta/conventions.md` and `CLAUDE.md` carry no note frontmatter.

### The changed set
`git status --porcelain=v1 -z --untracked-files=all` against `HEAD`, read without rename detection, so a rename is a deletion plus an addition. Deleted paths feed `deletions`; existing paths feed the other checks. Files under `attachments/` are binary by design: `secrets` and `schema` skip them; every other changed file must decode as UTF-8 or the check fails.
- Rejected: `git diff --cached` only. Capture writes files without staging them.
- Rejected: scanning attachments as bytes. The patterns would hit compressed data at random.

### Links
Markdown inline links `[text](target)` and reference links `[id]: target`. A target with a URL scheme (`https:`, `mailto:` and so on) or starting with `#` is skipped; a `#fragment` is stripped; the rest resolves relative to the linking file, or to the repo top level when it starts with `/`.
- Rejected: wiki links. No decision names them, and adding a syntax later is cheap.

### Secret patterns
- API keys: known prefixes (`sk-`, `sk-ant-`, `ghp_`, `gho_`, `github_pat_`, `AKIA`, `xox[bp]-`) followed by their usual length of key characters, and `api[_-]?key`, `secret` or `token` followed by `:` or `=` and 16 or more key characters.
- Private keys: a `-----BEGIN ... PRIVATE KEY-----` line.
- Card numbers: 13–19 digits in groups separated by spaces or dashes, where masking characters (`*`, `x`, `X`, `•`) may replace digits, and at least the first and last four characters are digits. No Luhn test, because a masked number cannot pass one and structure Q8 blocks masked numbers too.
- IBANs: two letters, two digits, then 11–30 letters or digits, optionally in groups of four; masking characters count as digits. No mod-97 test, for the same reason.
- Rejected: a pattern file in `conventions/`. Recall must apply the same patterns when it redacts (structure Q15), so they live in the script and recall calls it.

### Save
Steps in order: refuse if `.git/rebase-merge`, `.git/rebase-apply` or `MERGE_HEAD` exists; `git pull --rebase --autostash`; on a non-zero exit, `git rebase --abort` (which restores the autostash) and stop; run the four checks; `git add -- <checked paths>` and `git rm --cached` for deleted ones; `git commit -m`; `git push`; then, whether or not anything was committed, push when the branch is ahead of its upstream. Every git call runs with `GIT_TERMINAL_PROMPT=0` and a 60-second subprocess timeout for pull and push. A timed-out pull is followed by `git rebase --abort` when a rebase was left behind.
- Rejected: commit first, then pull. Structure Q13 fixed the order, and checking before committing keeps a failing note out of history.
- Rejected: retrying a rejected push. One user; the next save pushes it.

### Repo root
`git rev-parse --show-toplevel` from the working folder, never the script's own location, because the script runs from a domain's `.claude/mnemo/scripts/`.

### Version bump test
Compares against `git merge-base HEAD main`; when `main` is missing (a bare scratch clone) the test fails rather than skips. It reads `VERSION` at the merge base with `git show`.

### Shipped-layout test
Scans text files under `mnemo-plugin/` for `.claude/skills/` and `.claude/mnemo/` paths and maps each to `mnemo-plugin/skills/` or `mnemo-plugin/mnemo/`. Replaces `claude plugin validate` (architecture Q14).

## Risks / Trade-offs

- [The API-key pattern hits a harmless `token: ...` line] → the false-positive measurement task runs on redacted copies before merge; the owner masks or rewords.
- [A secret inside an attachment is not caught] → accepted: attachments are binary, and capture's own rule keeps secrets out of notes.

## Migration Plan

The first task group moves `plugins/mnemo/skills/README.md` to `mnemo-plugin/skills/README.md` (the only file there), removes the two manifests, adds `VERSION` at `0.2.0` (the manifest was at `0.1.1`; this change breaks the install), and updates `CLAUDE.md`, `README.md` and `cla.io/project-facts.md`. Rollback is a revert of the PR.
